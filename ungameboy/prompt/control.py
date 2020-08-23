from bisect import bisect
from prompt_toolkit.layout.controls import UIContent, UIControl
from typing import List

from .lexer import render_data
from ..address import Address
from ..disassembler import AssemblyView, Disassembler, ViewItem


NO_ROM = UIContent(
    lambda _: [('', "No ROM loaded")],
    line_count=1,
    show_cursor=False,
)


class AsmControl(UIControl):
    padding = 64
    bs = 256

    def __init__(self, view: AssemblyView):
        self.view = view
        self.scroll_index = 0
        self.scroll_pos = 0
        self.height = 1

        self._buffer: List[ViewItem] = []
        self.refresh()

    def is_focusable(self) -> bool:
        return True

    def create_content(self, width: int, height: int) -> "UIContent":
        if not self.view.asm.is_loaded:
            return NO_ROM

        if self.height != height:
            self.height = height
            self.refresh()

        lines = []
        pos = self.scroll_pos
        for item in self[pos:pos + self.height]:
            lines.extend(render_data(item.data))

        return UIContent(
            lines.__getitem__,
            line_count=len(lines),
            show_cursor=False,
        )

    def __getitem__(self, item):
        return self._buffer[item]

    def __len__(self):
        return len(self._buffer)

    @property
    def start_index(self):
        if not self._buffer:
            return self.scroll_index
        return self[0].item_index

    @property
    def end_index(self):
        if not self._buffer:
            return self.scroll_index
        return self[-1].next_index

    def refresh(self):
        """Clear the buffer and re-render from the current index"""
        self._buffer.clear()
        self.scroll_pos = 0
        if not self.view.asm.is_loaded:
            return

        for data in self.view[self.scroll_index:]:
            self._buffer.append(data)
            if len(self) >= self.height:
                break
        else:
            # Reached end of ROM: force window up
            self.move_up(self.height - len(self))

        self._extend_down(self[self.height - 1].next_index + self.padding)
        self._extend_up(self.scroll_index - self.padding)

    def index_position(self, index: int):
        """Find the position that corresponds to a given index"""
        if not self.start_index <= index < self.end_index:
            raise IndexError()

        # The elements in the buffer should always be sorted by index
        # in a strictly increasing order. This means that we can apply
        # the bisection method to find the index efficiently.
        a, b = 0, len(self) - 1
        while True:
            pivot = a + (b - a) // 2
            data = self[pivot]
            if data.item_index <= index < data.next_index:
                return pivot
            if data.item_index < index:
                a = pivot + 1
            else:
                b = pivot - 1

    def _extend_down(self, new_end_index: int):
        """
        Extend the buffer with new lines such that the given index is
        covered. Extensions are done in blocks of 256 bytes.
        """
        if self.end_index == len(self.view):
            return
        if new_end_index <= self.end_index:
            return
        if new_end_index > len(self.view):
            new_end_index = len(self.view)
        # Round up to nearest block
        new_end_index = ((new_end_index - 1) // self.bs + 1) * self.bs

        new_block = []
        for data in self.view[self.end_index:]:
            new_block.append(data)
            if data.next_index >= new_end_index:
                break

        self._buffer.extend(new_block)

    def _extend_up(self, new_start_index: int):
        """
        Add new data to the start of the buffer such that the given
        index is covered.
        """
        if new_start_index >= self.start_index:
            return
        if new_start_index < 0:
            new_start_index = 0
        # Round down to nearest block
        new_start_index = (new_start_index // self.bs) * self.bs

        # Adding data at the start of the buffer is a little tricky,
        # because it is possible for the start of the existing buffer
        # to not match the end of the new data (e.g. if previous block
        # boundary landed in the middle of a multi-byte instruction).
        # So this code keeps taking elements until the indices match.
        trim = 0
        target_index = self[trim].item_index

        new_block = []
        for data in self.view[new_start_index:]:
            new_block.append(data)

            if data.next_index < target_index:
                # Not enough new elements yet
                continue

            while data.next_index > target_index:
                # Mismatch between old and new data: mark the head
                # element for removal.
                trim += 1
                target_index = self[trim].item_index

            if data.next_index == target_index:
                break

        self._buffer = new_block + self._buffer[trim:]

        if self.scroll_pos < trim:
            # If the cursor was in the overlap, look up its new position
            self.scroll_pos = self.index_position(self.scroll_index)
        else:
            self.scroll_pos += len(new_block) - trim

    def _trim_up(self):
        """Remove unneeded buffer space at the start"""
        window_start = self.scroll_index - self.padding

        if window_start - self.start_index >= self.bs:
            # New start index, rounded down to the block
            target_start = (window_start // self.bs) * self.bs
            start_pos = self.index_position(target_start)

            self.scroll_pos -= start_pos
            self._buffer = self._buffer[start_pos:]

    def _trim_down(self):
        """Remove unneeded buffer space at the end"""
        end_pos = min(len(self), self.scroll_pos + self.height)
        end_index = self[end_pos - 1].next_index + self.padding

        if self.end_index - end_index >= self.bs:
            # New end index, rounded up to the block
            target_end = ((end_index - 1) // self.bs + 1) * self.bs
            self._buffer = self._buffer[:self.index_position(target_end)]

    def move_down(self, count: int):
        """Scroll down the display window by a given # of elements"""
        while count > 0:
            # Limit the move requested to how many lines are available
            # in the buffer, window size taken into account. Large moves
            # may need to be done in several steps, hence the loop.
            new_pos = min(
                len(self) - self.height,
                self.scroll_pos + count
            )
            count -= new_pos - self.scroll_pos

            self.scroll_pos = new_pos
            self.scroll_index = self[new_pos].item_index

            end_index = self[new_pos + self.height - 1].next_index
            self._extend_down(end_index + self.padding)
            self._trim_up()

            if end_index >= len(self.view):
                return

    def move_up(self, count: int):
        """Scroll up the display window by a given # of elements"""
        while count > 0:
            # Limit the move requested to how many lines are available
            # in the buffer, window size taken into account. Large moves
            # may need to be done in several steps, hence the loop.
            new_pos = max(0, self.scroll_pos - count)
            count -= self.scroll_pos - new_pos

            self.scroll_pos = new_pos
            self.scroll_index = self[new_pos].item_index

            self._extend_up(self.scroll_index - self.padding)
            self._trim_down()

            if self.scroll_index == 0:
                count = 0

    def move_to(self, index: int):
        distance = index - self.scroll_index
        # The use of padding as limit for the relative moves is
        # completely arbitrary, and incorrect. That's OK.
        if 0 <= distance <= self.padding:  # New pos is lower
            self.move_down(distance)
        elif 0 < -distance <= self.padding:  # New pos is higher
            self.move_up(-distance)
        else:
            index = max(0, min(index, len(self.view)))
            self.scroll_index = index
            self.refresh()

    def seek(self, address):
        index = self.view.address_to_index(address)
        if index is None:
            raise ValueError("Not a valid address for this scope")
        self.move_to(index)


class AsmControlV2(UIControl):
    def __init__(self, asm: Disassembler):
        self.asm = asm
        self.lines_count: int = 0
        self.lines_map: List[Address] = []

    def refresh(self):
        lines = []

        offset = 0
        rom_size = len(self.asm.rom)
        next_data = self.asm.data.next_block(Address.from_rom_offset(0))
        next_data_offset = (
            rom_size
            if next_data is None
            else next_data.address.rom_file_offset
        )
        _size_of = self.asm.rom.size_of

        while offset < rom_size:
            address = Address.from_rom_offset(offset)

            if offset >= next_data_offset:
                offset = next_data_offset

                lines.extend([address, address])
                offset += next_data.length
                next_data = self.asm.data.next_block(
                    Address.from_rom_offset(offset)
                )
                next_data_offset = (
                    rom_size
                    if next_data is None
                    else next_data.address.rom_file_offset
                )

            else:
                lines.append(address)
                offset += _size_of(offset)

        for section in self.asm.sections.list_sections():
            pos = bisect(lines, section.address)
            lines.insert(pos, section.address)

        for label in self.asm.labels.list_items():
            pos = bisect(lines, label.address)
            lines.insert(pos, label.address)

        self.lines_map = lines
        self.lines_count = len(lines)

    def get_line(self, line: int):
        addr = self.lines_map[line]
        ref_line = line
        while ref_line > 0 and self.lines_map[ref_line - 1] == addr:
            ref_line -= 1

        lines = render_data(self.asm[addr])
        return lines[line - ref_line]

    def create_content(self, width: int, height: int) -> UIContent:
        self.refresh()

        return UIContent(self.get_line, self.lines_count, show_cursor=False)
