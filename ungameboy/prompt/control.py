from bisect import bisect_right
from typing import TYPE_CHECKING, List, Optional, Tuple

from prompt_toolkit.application import get_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.controls import UIContent, UIControl

from .common import ControlMode
from .lexer import AssemblyRender
from ..address import ROM, Address, MemoryType
from ..data_structures import StateStack
from ..dis import Disassembler, RomElement

if TYPE_CHECKING:
    from prompt_toolkit.layout import Window


class AsmControl(UIControl):

    def __init__(self, asm: 'Disassembler'):
        from .key_bindings import create_asm_control_bindings

        self.asm = asm
        self.renderer = AssemblyRender(self)
        self.key_bindings = create_asm_control_bindings(self)

        self.current_zone: Tuple[MemoryType, int] = (ROM, 0)
        self.current_view = AsmRegionView(self, ROM, 0)

        self.mode = ControlMode.Default
        self._reset_scroll = False

        self.comment_buffer = ''
        self.cursor_y = 0
        self.cursor_x = 0

        self._stack: StateStack[Address] = StateStack()
        self._stack.push(Address(ROM, 0, 0))

        self.load_zone(self.current_zone)

    def get_key_bindings(self):
        return self.key_bindings

    def create_content(self, width: int, height: int) -> UIContent:
        return UIContent(
            self.get_line,
            self.current_view.lines,
            cursor_position=Point(0, self.cursor),
            show_cursor=False,
        )

    def get_line(self, line: int):
        try:
            addr, ref_line = self.current_view.get_line_info(line)
        except IndexError:
            return []
        return self.renderer.render(addr)[line - ref_line]

    def is_focusable(self) -> bool:
        return True

    def load_zone(self, zone: Tuple[MemoryType, int]):
        self.current_zone = zone
        self.current_view = AsmRegionView(self, *zone)

    def refresh(self):
        self.current_view.refresh()

    @property
    def default_mode(self) -> bool:
        return self.mode is ControlMode.Default

    @property
    def cursor_mode(self) -> bool:
        return self.mode is ControlMode.Cursor

    @property
    def comment_mode(self) -> bool:
        return self.mode is ControlMode.Comment

    @property
    def comment_index(self) -> Tuple[Address, Optional[int]]:
        addr, ref_line = self.current_view.get_line_info(self.cursor)
        if not self.comment_mode:
            return addr, None
        index = self.renderer.get_comment_index(addr, self.cursor - ref_line)
        return addr, index

    @property
    def address(self) -> Address:
        return self._stack.head

    @property
    def cursor(self) -> int:
        return self.cursor_y

    @cursor.setter
    def cursor(self, value: int):
        new_address = self.current_view.find_address(value)

        if self.comment_mode:
            self.save_comment()

        self._stack.head = new_address
        self.cursor_y = value

        if self.comment_mode:
            self.load_comment()

    @property
    def destination_address(self) -> Optional[Address]:
        item = self.asm[self.address]
        if isinstance(item, RomElement):
            return item.dest_address
        else:
            return None

    def get_vertical_scroll(self, window: "Window") -> int:
        if self.default_mode or self._reset_scroll:
            self._reset_scroll = False
            return self.cursor
        return window.vertical_scroll

    def toggle_cursor_mode(self):
        if self.cursor_mode:
            # Make transition back to screen mode seamless by setting
            # the cursor to the position at the top of the screen
            window = get_app().layout.current_window
            if window.content is self:
                self.cursor = window.vertical_scroll
            self.mode = ControlMode.Default

        else:
            self.mode = ControlMode.Cursor

    def _seek(self, address: Address):
        zone = (address.type, address.bank)
        if self.current_zone != zone:
            self.load_zone(zone)
        self._reset_scroll = True
        self.cursor = self.current_view.find_line(address)

    def seek(self, address: Address):
        if address.bank < 0:
            raise ValueError("Cannot seek address with missing ROM bank")
        if address.type is not ROM:
            raise NotImplementedError()
        self._stack.push(address)
        self._seek(address)

    def undo_seek(self):
        if not self._stack.can_undo:
            return
        self._seek(self._stack.undo())

    def redo_seek(self):
        if not self._stack.can_redo:
            return
        self._seek(self._stack.redo())

    def follow_jump(self):
        if self.destination_address is not None:
            self.seek(self.destination_address)

    def move_up(self, lines: int):
        cursor = max(0, self.cursor - lines)
        if cursor == self.cursor or lines <= 0:
            return

        found_line = self.mode is ControlMode.Default
        while not found_line:
            address, ref_line = self.current_view.get_line_info(cursor)
            valid_lines = self.renderer.get_valid_lines(address, self.mode)

            ref_line += len(valid_lines) - 1
            valid_lines.reverse()
            try:
                cursor = ref_line - valid_lines.index(True, ref_line - cursor)
                found_line = True
            except ValueError:
                cursor = ref_line - len(valid_lines)
                if cursor < 0:
                    return  # At start, can't move

        self.cursor = cursor

    def move_down(self, lines: int):
        cursor = min(self.current_view.lines - 1, self.cursor + lines)
        if cursor == self.cursor or lines <= 0:
            return

        found_line = self.mode is ControlMode.Default
        while not found_line:
            address, ref_line = self.current_view.get_line_info(cursor)
            valid_lines = self.renderer.get_valid_lines(address, self.mode)

            try:
                cursor = ref_line + valid_lines.index(True, cursor - ref_line)
                found_line = True
            except ValueError:
                cursor = ref_line + len(valid_lines)
                if cursor >= self.current_view.lines:
                    return  # At end, can't move

        self.cursor = cursor

    def move_left(self, move: int):
        if move <= 0:
            return
        if self.comment_mode:
            self.cursor_x = max(0, self.cursor_x - 1)

    def move_right(self, move: int):
        if move <= 0:
            return
        if self.comment_mode:
            self.cursor_x = min(
                len(self.comment_buffer), self.cursor_x + 1
            )

    # Commenting

    def enter_comment_mode(self):
        self.load_comment()
        self.mode = ControlMode.Comment

    def exit_comment_mode(self):
        self.save_comment()
        self.mode = ControlMode.Cursor

    def load_comment(self):
        addr, index = self.comment_index
        if index is None:
            comment = ''
        elif index < 0:
            comment = self.asm.comments.inline.get(addr, '')
        else:
            block = self.asm.comments.blocks.get(addr, [])
            comment = block[index] if index < len(block) else ''

        self.comment_buffer = comment
        self.cursor_x = min(self.cursor_x, len(comment))

    def save_comment(self):
        addr, index = self.comment_index
        if index is None:
            return
        elif index < 0:
            self.asm.comments.set_inline(addr, self.comment_buffer)
        else:
            self.asm.comments.set_block_line(addr, index, self.comment_buffer)

    def insert_str(self, data: str):
        comment, x = self.comment_buffer, self.cursor_x

        pos = max(x, 0)
        self.comment_buffer = comment[:pos] + data + comment[pos:]
        self.cursor_x += len(data)

    def delete_before(self, count=1):
        comment, x = self.comment_buffer, self.cursor_x

        pos = max(x - count, 0)
        self.comment_buffer = comment[:pos] + comment[x:]
        self.cursor_x = pos

    def delete_after(self, count=1):
        comment, x = self.comment_buffer, self.cursor_x

        pos = min(x + count, len(comment))
        self.comment_buffer = comment[:x] + comment[pos:]


class AsmRegionView:
    def __init__(self, control: AsmControl, m_type: MemoryType, m_bank: int):
        self.control = control
        self.mem_type = m_type
        self.mem_bank = m_bank

        self._lines: List[int] = []
        self._addr: List[Address] = []
        self.lines: int = 0

        self.refresh()

    def refresh(self):
        self.build_lines_map()

    def build_lines_map(self):
        self._lines.clear()
        self._addr.clear()

        lines = 0
        address = Address(self.mem_type, self.mem_bank, 0)
        end_addr = address.zone_end + 1
        count_lines = self.control.renderer.get_lines_count

        while address < end_addr:
            self._lines.append(lines)
            self._addr.append(address)

            lines, address = count_lines(address)
            lines += self._lines[-1]

        self.lines = lines

    def get_line_info(self, line: int) -> Tuple[Address, int]:
        """
        Given a line number in the resulting document, get the address
        to query and at while line that block is referenced.
        """
        pos = bisect_right(self._lines, line)
        if pos == 0:
            raise IndexError(line)

        return self._addr[pos - 1], self._lines[pos - 1]

    def find_address(self, line: int) -> Address:
        pos = bisect_right(self._lines, line)
        return self._addr[max(0, pos - 1)]

    def find_line(self, address: Address) -> int:
        if (address.type, address.bank) != (self.mem_type, self.mem_bank):
            raise KeyError(f"Address {address} is not in this region")
        pos = bisect_right(self._addr, address)
        return 0 if pos == 0 else self._lines[pos - 1]
