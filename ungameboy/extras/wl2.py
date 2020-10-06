from typing import TYPE_CHECKING

from ..address import Address
from ..dis.data import DataContent, DataProcessor
from ..scripts import asm_script

if TYPE_CHECKING:
    from ..dis import Disassembler, ROMBytes


class RunLengthEncodingProcessor(DataProcessor):
    slug = "wl2.rle"

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
    slug = "wl2.rlei"

    def __init__(self, data_size: int):
        self.data_size = data_size

    def dump(self):
        return f"{self.slug}:{self.data_size}"

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


@asm_script
def rle_block(asm: "Disassembler", address: Address):
    rle = RunLengthEncodingProcessor()
    asm.data.create(address, DataContent, processor=rle)
