from bisect import bisect_right
from enum import Enum, auto
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from prompt_toolkit.application import get_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.controls import UIContent, UIControl

from .lexer import AssemblyRender
from ..address import ROM, Address, MemoryType
from ..data_structures import StateStack
from ..dis import BinaryData, CartridgeHeader, Disassembler, EmptyData, RomElement

if TYPE_CHECKING:
    from prompt_toolkit.layout import Window
    from .application import DisassemblyEditor


class ControlMode(Enum):
    Default = auto()
    Cursor = auto()
    Comment = auto()


class AsmControl(UIControl):
    _ZONES: Dict[Tuple[MemoryType, int], "AsmRegionView"] = {}

    def __init__(self, app: 'DisassemblyEditor'):
        from .key_bindings import create_asm_control_bindings

        self.app = app
        self.asm = app.disassembler
        self.key_bindings = create_asm_control_bindings(self)

        self.current_zone: Tuple[MemoryType, int] = (ROM, 0)
        self.current_view = AsmRegionView(self.asm, ROM, 0)

        self.mode = ControlMode.Default
        self._reset_scroll = False

        self.comment_buffer = ''
        self.sub_cursor_x = 0

        self._stack: StateStack[Address] = StateStack()
        self._stack.push(Address(ROM, 0, 0))

        self.renderer = AssemblyRender(self)

        self.load_zone(self.current_zone)

    def get_key_bindings(self):
        return self.key_bindings

    def create_content(self, width: int, height: int) -> UIContent:
        return UIContent(
            self.get_line,
            self.current_view.lines_count,
            cursor_position=Point(0, self.cursor_position),
            show_cursor=False,
        )

    def get_line(self, line: int):
        try:
            addr, offset = self.current_view.get_line_info(line)
        except IndexError:
            return []
        return self.renderer.render(addr)[offset]

    def is_focusable(self) -> bool:
        return True

    @classmethod
    def _get_zone(cls, asm: Disassembler, zone: Tuple[MemoryType, int]):
        if zone not in cls._ZONES:
            cls._ZONES[zone] = AsmRegionView(asm, *zone)
        return cls._ZONES[zone]

    def load_zone(self, zone: Tuple[MemoryType, int]):
        self.current_zone = zone
        self.current_view = self._get_zone(self.asm, zone)
        self.refresh()

    def refresh(self):
        self.current_view.build_names_map()

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
    def cursor(self) -> Address:
        return self._stack.head

    @cursor.setter
    def cursor(self, value: Address):
        if self.comment_mode:
            self.asm.comments.set_inline(self.cursor, self.comment_buffer)
            self.comment_buffer = self.asm.comments.inline.get(value, "")
            self.sub_cursor_x = min(self.sub_cursor_x, len(self.comment_buffer))
        self._stack.head = value

    @property
    def cursor_position(self) -> int:
        return self.current_view.find_line(self.cursor)

    @property
    def cursor_destination(self) -> Optional[Address]:
        item = self.asm[self.cursor]
        if isinstance(item, RomElement):
            return item.dest_address
        else:
            return None

    def get_vertical_scroll(self, window: "Window") -> int:
        if self.default_mode or self._reset_scroll:
            self._reset_scroll = False
            return self.cursor_position
        return window.vertical_scroll

    def toggle_cursor_mode(self):
        if self.cursor_mode:
            # Make transition back to screen mode seamless by setting
            # the cursor to the position at the top of the screen
            window = get_app().layout.current_window
            if window.content is self:
                scroll = window.vertical_scroll
                self.cursor = self.current_view.find_address(scroll)
            self.mode = ControlMode.Default

        else:
            self.mode = ControlMode.Cursor

    def _seek(self, address: Address):
        zone = (address.type, address.bank)
        if self.current_zone != zone:
            self.load_zone(zone)
        self._reset_scroll = True
        self.cursor = address

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
        if self.cursor_destination is not None:
            self.seek(self.cursor_destination)

    def move_up(self, lines: int):
        if lines <= 0:
            return
        view = self.current_view
        self.cursor = view.get_relative_address(self.cursor, -lines)

    def move_down(self, lines: int):
        if lines <= 0:
            return
        view = self.current_view
        self.cursor = view.get_relative_address(self.cursor, lines)

    def move_left(self, move: int):
        if move <= 0:
            return
        if self.comment_mode:
            self.sub_cursor_x = max(0, self.sub_cursor_x - 1)

    def move_right(self, move: int):
        if move <= 0:
            return
        if self.comment_mode:
            self.sub_cursor_x = min(
                len(self.comment_buffer), self.sub_cursor_x + 1
            )

    # Commenting

    def enter_comment_mode(self):
        self.comment_buffer = self.asm.comments.inline.get(self.cursor, '')
        self.sub_cursor_x = min(self.sub_cursor_x, len(self.comment_buffer))
        self.mode = ControlMode.Comment

    def exit_comment_mode(self):
        self.asm.comments.set_inline(self.cursor, self.comment_buffer)
        self.mode = ControlMode.Cursor

    def insert_str(self, data: str):
        comment, x = self.comment_buffer, self.sub_cursor_x

        pos = max(x, 0)
        self.comment_buffer = comment[:pos] + data + comment[pos:]
        self.sub_cursor_x += len(data)

    def delete_before(self, count=1):
        comment, x = self.comment_buffer, self.sub_cursor_x

        pos = max(x - count, 0)
        self.comment_buffer = comment[:pos] + comment[x:]
        self.sub_cursor_x = pos

    def delete_after(self, count=1):
        comment, x = self.comment_buffer, self.sub_cursor_x

        pos = min(x + count, len(comment))
        self.comment_buffer = comment[:x] + comment[pos:]


class AsmRegionView:
    def __init__(self, asm: Disassembler, m_type: MemoryType, m_bank: int):
        self.asm = asm
        self.mem_type = m_type
        self.mem_bank = m_bank

        self._lines: List[int] = []
        self._addr: List[Address] = []
        self.lines_count: int = 0

        self.build_names_map()

    def build_names_map(self):
        self._lines.clear()
        self._addr.clear()

        address = Address(self.mem_type, self.mem_bank, 0)
        end_addr = address.zone_end + 1

        n_lines = 0
        asm = self.asm
        next_data = asm.data.next_block(address)
        next_data_addr = (
            end_addr if next_data is None else next_data.address
        )
        _is_rom = self.mem_type is ROM
        _size_of = asm.rom.size_of

        while address < end_addr:
            self._lines.append(n_lines)
            self._addr.append(address)

            if asm.sections.get_section(address) is not None:
                n_lines += 1

            calls = asm.xrefs.count_incoming('call', address)
            n_lines += calls if calls <= 3 else 1
            jumps = asm.xrefs.count_incoming('jump', address)
            n_lines += jumps if jumps <= 3 else 1

            n_lines += len(asm.labels.get_labels(address))
            n_lines += len(asm.comments.blocks.get(address, ()))

            if address >= next_data_addr and next_data is not None:
                address = next_data.address

                if isinstance(next_data, BinaryData):
                    n_lines += 2
                    for row in range(1, next_data.rows):
                        address = address + next_data.row_size
                        self._lines.append(n_lines)
                        self._addr.append(address)
                        n_lines += len(asm.comments.blocks.get(address, ()))
                        n_lines += 1
                elif isinstance(next_data, EmptyData):
                    n_lines += 1
                elif isinstance(next_data, CartridgeHeader):
                    n_lines += 5

                address = next_data.address + next_data.size

                next_data = asm.data.next_block(address)
                next_data_addr = (
                    end_addr if next_data is None else next_data.address
                )

            elif _is_rom:
                n_lines += 1
                address += _size_of(address.rom_file_offset)

            else:
                n_lines += 1
                address += 1

        self.lines_count = n_lines

    def get_line_info(self, line: int) -> Tuple[Address, int]:
        """
        Given a line number in the resulting document, get the address
        to query and which line of the result to use.
        """
        pos = bisect_right(self._lines, line)
        if pos == 0:
            raise IndexError(line)

        addr = self._addr[pos - 1]
        ref_line = self._lines[pos - 1]
        return addr, line - ref_line

    def get_relative_address(self, address: Address, offset: int) -> Address:
        pos = bisect_right(self._addr, address)
        pos += offset - 1
        return self._addr[max(0, min(pos, len(self._addr) - 1))]

    def find_address(self, line: int) -> Address:
        pos = bisect_right(self._lines, line)
        return self._addr[max(0, pos - 1)]

    def find_line(self, address: Address) -> int:
        if (address.type, address.bank) != (self.mem_type, self.mem_bank):
            raise KeyError(f"Address {address} is not in this region")
        pos = bisect_right(self._addr, address)
        return 0 if pos == 0 else self._lines[pos - 1]
