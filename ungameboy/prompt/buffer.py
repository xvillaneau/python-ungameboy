from typing import List

from ..disassembler import Disassembler, AsmData


class AsmBuffer:
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
        self._buffer.clear()
        self.scroll_index = 0

        for data in self.asm[self.scroll_address:]:
            self._buffer.append(data)
            if len(self) >= self.height:
                break
        else:
            self.move_up(self.height - len(self))

        self._extend_down(self[self.height - 1].next_address + self.padding)
        self._extend_up(self.scroll_address - self.padding)

    def address_index(self, address: int):
        if not self.start_address <= address < self.end_address:
            raise IndexError()
        a, b = 0, len(self) - 1
        while True:
            pivot = a + (b - a) // 2
            data = self[pivot]
            if data.address <= address < data.next_address:
                return pivot
            if data.binary.address < address:
                a = pivot + 1
            else:
                b = pivot - 1

    def _extend_down(self, new_end_address: int):
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
        if new_start_address >= self.start_address:
            return
        if new_start_address < 0:
            new_start_address = 0
        # Round down to nearest block
        new_start_address = (new_start_address // 256) * 256

        lines_trim = 0
        target_address = self[lines_trim].address
        new_block = []

        for data in self.asm[new_start_address:]:
            new_block.append(data)

            if data.next_address < target_address:
                continue

            while data.next_address > target_address:
                lines_trim += 1
                target_address = self[lines_trim].address

            if data.next_address == target_address:
                break

        self._buffer = new_block + self._buffer[lines_trim:]

        if self.scroll_index < lines_trim:
            self.scroll_index = self.address_index(self.scroll_address)
        else:
            self.scroll_index += len(new_block) - lines_trim

    def _trim_up(self):
        window_start = self.scroll_address - self.padding
        if window_start - self.start_address >= 256:
            target_start = (window_start // 256) * 256
            start_pos = self.address_index(target_start)

            self.scroll_index -= start_pos
            self._buffer = self._buffer[start_pos:]

    def _trim_down(self):
        end_index = min(len(self), self.scroll_index + self.height)
        window_end = self[end_index - 1].next_address + self.padding
        if self.end_address - window_end >= 256:
            target_end = ((window_end - 1) // 256 + 1) * 256
            end_pos = self.address_index(target_end)
            self._buffer = self._buffer[:end_pos]

    def move_down(self, lines: int):
        while lines > 0:
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
        while lines > 0:
            new_pos = max(0, self.scroll_index - lines)
            lines -= self.scroll_index - new_pos

            self.scroll_index = new_pos
            self.scroll_address = self[new_pos].address

            self._extend_up(self.scroll_address - self.padding)
            self._trim_down()

            if self.scroll_address == 0:
                lines = 0
