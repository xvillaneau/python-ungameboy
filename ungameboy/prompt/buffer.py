from typing import List

from ..disassembler import AssemblyView, ViewItem


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

    def __init__(self, view: AssemblyView, index=0, height=1):
        self.view = view
        self.scroll_index = index
        self.scroll_pos = 0
        self.height = height

        self._buffer: List[ViewItem] = []
        self.refresh()

    def __getitem__(self, item):
        return self._buffer[item]

    def __len__(self):
        return len(self._buffer)

    def window(self):
        return self[self.scroll_pos:self.scroll_pos + self.height]

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
        if not self.view.asm.is_ready:
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
