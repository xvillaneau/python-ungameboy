from typing import TYPE_CHECKING

from ..address import Address
from ..dis import BinaryData
from ..scripts import asm_script

if TYPE_CHECKING:
    from ..dis import Disassembler, ROMBytes


def rle_decompress(rom: "ROMBytes", address: Address):
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


@asm_script
def rle_block(asm: "Disassembler", address: Address):
    unpacked_data, size = rle_decompress(asm.rom, address)

    block = BinaryData(address, size)
    block.description = "Run-Length Encoded Data"
    asm.data.insert(block)
