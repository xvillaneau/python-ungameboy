from bisect import bisect_right
from typing import TYPE_CHECKING, Dict, List, Tuple

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
        self.load_zone(self.current_zone)

    def create_content(self, width: int, height: int) -> UIContent:
        return UIContent(
            self.current_view.get_line,
            self.current_view.lines_count,
            cursor_position=Point(0, self.current_view.cursor_line),
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
            self.views[zone] = AsmRegionView(self.asm, *zone)

    def refresh(self):
        self.current_view.build_names_map()

    def get_vertical_scroll(self, _: "Window") -> int:
        return self.current_view.cursor_line

    def seek(self, address: Address):
        if address.bank < 0:
            raise ValueError("Cannot seek address with missing ROM bank")
        zone = (address.type, address.bank)
        if self.current_zone != zone:
            self.load_zone(zone)
        self.current_view.cursor = address


class AsmRegionView:
    def __init__(self, asm: "Disassembler", mem_type: MemoryType, mem_bank: int = 0):
        self.asm = asm
        self.mem_type = mem_type
        self.mem_bank = mem_bank

        self.cursor = Address(mem_type, mem_bank, 0)

        self._lines: List[int] = []
        self._addr: List[int] = []
        self.lines_count: int = 0

        self.build_names_map()

    @property
    def cursor_line(self) -> int:
        pos = bisect_right(self._addr, self.cursor)
        if pos == 0:
            return 0
        else:
            return self._lines[pos - 1]

    def build_names_map(self):
        self._lines.clear()
        self._addr.clear()

        address = Address(self.mem_type, self.mem_bank, 0)
        end_addr = address.zone_end + 1

        n_lines = 0
        next_data = self.asm.data.next_block(address)
        next_data_addr = (
            end_addr if next_data is None else next_data.address
        )
        _is_rom = self.mem_type is ROM
        _size_of = self.asm.rom.size_of

        while address < end_addr:
            self._lines.append(n_lines)
            self._addr.append(address)

            if self.asm.sections.get_section(address) is not None:
                n_lines += 1
            n_lines += len(self.asm.labels.get_labels(address))

            if address >= next_data_addr:
                n_lines += 2
                address = next_data.next_address

                next_data = self.asm.data.next_block(address)
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

        lines = render_data(self.asm[addr])
        return lines[line - ref_line]

    def move_up(self, lines: int):
        if lines <= 0:
            return
        pos = bisect_right(self._addr, self.cursor)
        self.cursor = self._addr[max(0, pos - lines - 1)]

    def move_down(self, lines: int):
        if lines <= 0:
            return
        pos = bisect_right(self._addr, self.cursor)
        self.cursor = self._addr[min(len(self._addr), pos + lines) - 1]
