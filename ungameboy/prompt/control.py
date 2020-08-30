from bisect import bisect_right
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from prompt_toolkit.application import get_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.controls import UIContent, UIControl

from .lexer import render_element
from ..address import ROM, Address, MemoryType
from ..data_structures import StateStack
from ..dis import DataRow, Disassembler, Instruction, Label

if TYPE_CHECKING:
    from prompt_toolkit.layout import Window


class AsmControl(UIControl):
    _ZONES: Dict[Tuple[MemoryType, int], "AsmRegionView"] = {}

    def __init__(self, asm: Disassembler):
        self.cursor_destination: Optional[Address]

        self.asm = asm

        self.current_zone: Tuple[MemoryType, int] = (ROM, 0)
        self.current_view = AsmRegionView(self.asm, ROM, 0)

        self.cursor_mode = False
        self._reset_scroll = False

        self._stack: StateStack[Address] = StateStack()
        self._stack.push(Address(ROM, 0, 0))
        self._update_cursor_destination()

        self.load_zone(self.current_zone)

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
        return render_element(addr, self)[offset]

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

    def refresh(self):
        self.current_view.build_names_map()

    @property
    def cursor(self) -> Address:
        return self._stack.head

    @cursor.setter
    def cursor(self, value: Address):
        self._stack.head = value
        self._update_cursor_destination()

    @property
    def cursor_position(self) -> int:
        return self.current_view.find_line(self.cursor)

    def _update_cursor_destination(self):
        self.cursor_destination = None

        item = self.asm[self.cursor]
        if isinstance(item, DataRow):
            # TODO: Deal with more than one address per row
            for value in item.values:
                if isinstance(value, Label):
                    value = value.address
                if isinstance(value, Address):
                    self.cursor_destination = value
                    break
            return
        if not isinstance(item, Instruction):
            return

        value = item.value
        if isinstance(value, Label):
            value = value.address
        if not isinstance(value, Address) or value.bank < 0:
            return

        if self.cursor not in self.asm.context.force_scalar:
            self.cursor_destination = value

    def get_vertical_scroll(self, window: "Window") -> int:
        if self.cursor_mode and not self._reset_scroll:
            return window.vertical_scroll
        else:
            self._reset_scroll = False
            return self.cursor_position

    def toggle_cursor_mode(self):
        if self.cursor_mode:
            # Make transition back to screen mode seamless by setting
            # the cursor to the position at the top of the screen
            window = get_app().layout.current_window
            if window.content is self:
                scroll = window.vertical_scroll
                self.cursor = self.current_view.find_address(scroll)

        self.cursor_mode = not self.cursor_mode

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
            xrefs = asm.xrefs.get_xrefs(address)
            n_lines += len(xrefs.called_by)
            n_lines += len(xrefs.jumps_from)
            n_lines += len(asm.labels.get_labels(address))

            if address >= next_data_addr and next_data is not None:
                n_lines += 2
                address = next_data.address

                for row in range(1, next_data.rows):
                    address = address + next_data.row_size
                    self._lines.append(n_lines)
                    self._addr.append(address)
                    n_lines += 1

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
