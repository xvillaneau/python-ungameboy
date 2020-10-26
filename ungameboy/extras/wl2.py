from typing import TYPE_CHECKING

from ..address import Address
from ..data_types import Byte, SignedByte
from ..dis.data import Data, DataProcessor, DataTable, JumpTableDetector
from ..scripts import asm_script

if TYPE_CHECKING:
    from ..dis import Disassembler, ROMBytes


class RunLengthEncodingProcessor(DataProcessor):
    name = "wl2.rle"

    def process(self, rom: 'ROMBytes', address: Address):
        data = []
        start_pos = pos = address.rom_file_offset

        byte = rom[pos]
        while byte != 0:
            pos += 1
            pkg_type, arg = divmod(byte, 0x80)

            if pkg_type > 0:  # Data
                data.extend(rom[pos:pos + arg])
                pos += arg
            else:  # RLE
                value = rom[pos]
                data.extend(value for _ in range(arg))
                pos += 1

            byte = rom[pos]

        return bytes(data), pos - start_pos + 1


class InterlacedRLEProcessor(DataProcessor):
    name = "wl2.rlei"

    def __init__(self, data_size: int):
        self.data_size = data_size

    def dump(self):
        return f"{self.name}:{self.data_size}"

    @classmethod
    def load(cls, args: str):
        size = int(args)
        return cls(size)

    def process(self, rom: 'ROMBytes', address: Address):
        data = []
        start_pos = pos = address.rom_file_offset
        byte = rom[pos]
        while byte != 0:
            pos += 1
            pkg_type, arg = divmod(byte, 0x80)
            remaining = self.data_size - len(data)

            if pkg_type > 0:  # Data
                packet = rom[pos:pos + arg]
                pos += min(arg, remaining)
            else:  # RLE
                packet = [rom[pos]] * arg
                pos += 1
            data.extend(packet[:remaining])

            if len(data) == self.data_size:
                break
            byte = rom[pos]
        else:
            pos += 1

        half = self.data_size // 2
        data = [
            data[i // 2 + half * (i % 2)]
            for i in range(self.data_size)
        ]

        return bytes(data), pos - start_pos


class WL2Sprite(Data):
    name = "wl2.sprite"

    def __init__(self, address: Address, size: int = 0):
        super().__init__(address, size)
        self.row_size = 4

    def populate(self, rom: 'ROMBytes'):

        if not self.size:
            start, offset = self.address.rom_file_offset, 0
            while rom[start + offset] != 0x80:
                offset += 4
            self.size = offset + 1

        super().populate(rom)
        if self.rom_bytes[-1] != 0x80:
            raise ValueError("Sprite data must end with $80")

    def save(self):
        return ('data', 'load', self.address, self.size, self.name)

    @classmethod
    def load(cls, address, size, args, processor) -> 'Data':
        return cls(address, size)

    def get_row_items(self, row: int):
        row_bin = self.get_row_bin(row)
        if row_bin == b'\x80':
            return [Byte(0x80)]
        x, y, n, f = row_bin
        return [SignedByte(x), SignedByte(y), Byte(n), Byte(f)]


@asm_script("wl2.sprites_table")
def detect_sprites_table(asm: 'Disassembler', address: Address):
    table = DataTable(address, 0, 'addr', JumpTableDetector())
    asm.data.insert(table)

    asm.labels.auto_create(address)

    visited = set()
    for row in table:
        ref = asm.context.detect_addr_bank(address, row.items[0])
        if ref in visited:
            continue
        visited.add(ref)

        asm.data.insert(WL2Sprite(ref))
        asm.labels.auto_create(ref, local=True)
