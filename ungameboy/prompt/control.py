from bisect import bisect_right
from typing import TYPE_CHECKING, Dict, List, Tuple

from prompt_toolkit.application import get_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.controls import UIContent, UIControl

from .lexer import render_data
from ..address import ROM, Address, MemoryType

if TYPE_CHECKING:
    from prompt_toolkit.layout import Window
    from ..disassembler import Disassembler


NO_ROM = UIContent(
    lambda _: [('', "No ROM loaded")],
    line_count=1,
    show_cursor=False,
)


class AsmControl(UIControl):
    def __init__(self, asm: "Disassembler"):
        self.asm = asm

        self.views: Dict[Tuple[MemoryType, int], AsmRegionView] = {}
        self.current_zone = (ROM, 0)

        self.cursor = Address(ROM, 0, 0)
        self.cursor_mode = False

        self.load_zone(self.current_zone)

    def create_content(self, width: int, height: int) -> UIContent:
        return UIContent(
            self.current_view.get_line,
            self.current_view.lines_count,
            cursor_position=Point(0, self.cursor_position),
            show_cursor=False,
        )

    def is_focusable(self) -> bool:
        return True

    @property
    def current_view(self) -> "AsmRegionView":
        return self.views[self.current_zone]

    def load_zone(self, zone: Tuple[MemoryType, int]):
        self.current_zone = zone
        if zone in self.views:
            self.refresh()
        else:
            self.views[zone] = AsmRegionView(self, *zone)

    def refresh(self):
        self.current_view.build_names_map()

    @property
    def cursor_position(self) -> int:
        return self.current_view.find_line(self.cursor)

    def get_vertical_scroll(self, window: "Window") -> int:
        if self.cursor_mode:
            return window.vertical_scroll
        else:
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

    def seek(self, address: Address):
        if address.bank < 0:
            raise ValueError("Cannot seek address with missing ROM bank")
        zone = (address.type, address.bank)
        if self.current_zone != zone:
            self.load_zone(zone)
        self.cursor = address

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
    def __init__(self, control: AsmControl, m_type: MemoryType, m_bank: int):
        self.ctrl = control
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
        asm = self.ctrl.asm
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
            n_lines += len(asm.labels.get_labels(address))

            if address >= next_data_addr:
                n_lines += 2
                address = next_data.next_address

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

    def get_line(self, line: int):
        pos = bisect_right(self._lines, line)
        if pos == 0:
            return []

        addr = self._addr[pos - 1]
        ref_line = self._lines[pos - 1]

        cursor = self.ctrl.cursor if self.ctrl.cursor_mode else None
        lines = render_data(self.ctrl.asm[addr], cursor)
        return lines[line - ref_line]

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
