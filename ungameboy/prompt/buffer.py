from typing import List

from ..disassembler import Disassembler, AsmData


class AsmBuffer:
    """
    Assembly code buffer

    This code handles most of the interaction between the UI and the
    disassembler. The core issue is that the disassembler thinks in
    bytes while the UI thinks in lines of text, and will need to do
    things like "move forward 7 lines".

    Moving forward from a known position is not too much of a problem
    however moving backwards is, since it is generally not possible to
    tell if any given byte of the ROM is a CPU instruction or one of
    its arguments. The solution used here works as follows: given the
    address of the first byte we'd like to display, look back 64 bytes
    (where possible) and get elements from there. This results in a
    short margin before the current screen in which lines are known.

    Since it would be expensive to ask the disassembler for data every
    time the display updates, this buffer maintains a cache of elements
    larger than the window of code requested. That cache is built and
    dropped in blocks of assembly elements equivalent to 256 bytes. This
    hopefully helps with performance, though I haven't checked.
    """
    padding = 64
    bs = 256

    def __init__(self, asm: Disassembler, address=0, height=1):
        self.asm = asm
        self.scroll_address = address
        self.scroll_index = 0
        self.height = height

        self._buffer: List[AsmData] = []
        self.refresh()

    def __getitem__(self, item):
        return self._buffer[item]

    def __len__(self):
        return len(self._buffer)

    def print_window(self):
        for instr in self.window():
            print(f'{instr.address:06x} {instr.bytes.hex():<6} {instr}')

    def window(self):
        return self[self.scroll_index:self.scroll_index + self.height]

    @property
    def start_address(self):
        if not self._buffer:
            return self.scroll_address
        return self[0].address

    @property
    def end_address(self):
        if not self._buffer:
            return self.scroll_address
        return self[-1].next_address

    def refresh(self):
        """Clear the buffer and re-render from the current address"""
        self._buffer.clear()
        self.scroll_index = 0

        for data in self.asm[self.scroll_address:]:
            self._buffer.append(data)
            if len(self) >= self.height:
                break
        else:
            # Reached end of ROM: force window up
            self.move_up(self.height - len(self))

        self._extend_down(self[self.height - 1].next_address + self.padding)
        self._extend_up(self.scroll_address - self.padding)

    def address_index(self, address: int):
        """Find the index that corresponds to a given index"""
        if not self.start_address <= address < self.end_address:
            raise IndexError()

        # The elements in the buffer should always be sorted by address
        # in a strictly increasing order. This means that we can apply
        # the bisection method to find the address efficiently.
        a, b = 0, len(self) - 1
        while True:
            pivot = a + (b - a) // 2
            data = self[pivot]
            if data.address <= address < data.next_address:
                return pivot
            if data.address < address:
                a = pivot + 1
            else:
                b = pivot - 1

    def _extend_down(self, new_end_address: int):
        """
        Extend the buffer with new lines such that the given address is
        covered. Extensions are done in blocks of 256 bytes.
        """
        if self.end_address == len(self.asm):
            return
        if new_end_address <= self.end_address:
            return
        if new_end_address > len(self.asm):
            new_end_address = len(self.asm)
        # Round up to nearest block
        new_end_address = ((new_end_address - 1) // self.bs + 1) * self.bs

        new_block = []
        for data in self.asm[self.end_address:]:
            new_block.append(data)
            if data.next_address >= new_end_address:
                break

        self._buffer.extend(new_block)

    def _extend_up(self, new_start_address: int):
        """
        Add new data to the start of the buffer such that the given
        address is covered.
        """
        if new_start_address >= self.start_address:
            return
        if new_start_address < 0:
            new_start_address = 0
        # Round down to nearest block
        new_start_address = (new_start_address // self.bs) * self.bs

        # Adding data at the start of the buffer is a little tricky,
        # because it is possible for the start of the existing buffer
        # to not match the end of the new data (e.g. if previous block
        # boundary landed in the middle of a multi-byte instruction).
        # So this code keeps taking elements until the addresses match.
        lines_trim = 0
        target_address = self[lines_trim].address

        new_block = []
        for data in self.asm[new_start_address:]:
            new_block.append(data)

            if data.next_address < target_address:
                # Not enough new elements yet
                continue

            while data.next_address > target_address:
                # Mismatch between old and new data: mark the head
                # element for removal.
                lines_trim += 1
                target_address = self[lines_trim].address

            if data.next_address == target_address:
                break

        self._buffer = new_block + self._buffer[lines_trim:]

        if self.scroll_index < lines_trim:
            # If the cursor was in the overlap, look up its new position
            self.scroll_index = self.address_index(self.scroll_address)
        else:
            self.scroll_index += len(new_block) - lines_trim

    def _trim_up(self):
        """Remove unneeded buffer space at the start"""
        window_start = self.scroll_address - self.padding

        if window_start - self.start_address >= self.bs:
            # New start address, rounded down to the block
            target_start = (window_start // self.bs) * self.bs
            start_pos = self.address_index(target_start)

            self.scroll_index -= start_pos
            self._buffer = self._buffer[start_pos:]

    def _trim_down(self):
        """Remove unneeded buffer space at the end"""
        end_index = min(len(self), self.scroll_index + self.height)
        window_end = self[end_index - 1].next_address + self.padding

        if self.end_address - window_end >= self.bs:
            # New end address, rounded up to the block
            target_end = ((window_end - 1) // self.bs + 1) * self.bs
            self._buffer = self._buffer[:self.address_index(target_end)]

    def move_down(self, lines: int):
        """Scroll down the display window by a given # of elements"""
        while lines > 0:
            # Limit the move requested to how many lines are available
            # in the buffer, window size taken into account. Large moves
            # may need to be done in several steps, hence the loop.
            new_pos = min(
                len(self) - self.height,
                self.scroll_index + lines
            )
            lines -= new_pos - self.scroll_index

            self.scroll_index = new_pos
            self.scroll_address = self[new_pos].address

            end_address = self[new_pos + self.height - 1].next_address
            self._extend_down(end_address + self.padding)
            self._trim_up()

            if end_address >= len(self.asm):
                return

    def move_up(self, lines: int):
        """Scroll up the display window by a given # of elements"""
        while lines > 0:
            # Limit the move requested to how many lines are available
            # in the buffer, window size taken into account. Large moves
            # may need to be done in several steps, hence the loop.
            new_pos = max(0, self.scroll_index - lines)
            lines -= self.scroll_index - new_pos

            self.scroll_index = new_pos
            self.scroll_address = self[new_pos].address

            self._extend_up(self.scroll_address - self.padding)
            self._trim_down()

            if self.scroll_address == 0:
                lines = 0
