from .instructions import CODE_POINTS, RawInstruction
from ..address import Address
from ..enums import Operation

__all__ = ['ROMBytes']


class ROMBytes:
    """
    Represents the raw ROM file. It's entirely stored in memory, though
    this object should be used to
    """

    def __init__(self, rom_file):
        # Just store the entire ROM in memory
        self.rom = rom_file.read()

    def __len__(self):
        return len(self.rom)

    def __getitem__(self, item):
        return self.rom[item]

    def size_of(self, offset: int) -> int:
        return CODE_POINTS[self.rom[offset]].length

    def decode_instruction(self, offset: int) -> RawInstruction:
        """
        Decode the instruction for which the code is at a given address.
        This may read more than one byte, or return invalid data.
        """
        if isinstance(offset, Address):
            addr = offset
            offset = addr.rom_file_offset
        else:
            addr = Address.from_rom_offset(offset)
        op = CODE_POINTS[self.rom[offset]]

        if op.length == 1:
            parameters = b''

        else:  # length >= 2
            parameters = bytes(self.rom[offset + 1:offset + op.length])

            if len(parameters) + 1 != op.length:
                binary = bytes(self.rom[offset:offset + op.length])
                return RawInstruction(
                    Operation.Invalid, (), addr, len(binary), binary
                )

        return op.make_instance(addr, parameters)


class HeaderDecoder:
    NINTENDO_LOGO = bytes.fromhex(
        'ceed6666cc0d000b03730083000c000d0008111f8889000e'
        'dccc6ee6ddddd999bbbb67636e0eecccdddc999fbbb9333e'
    )

    ROM_BANKS = {
        0x00: 0, 0x01: 4, 0x02: 8,
        0x03: 16, 0x04: 32, 0x05: 64,
        0x06: 128, 0x07: 256, 0x08: 512,
        0x52: 72, 0x53: 80, 0x54: 96,
    }
    SRAM_SIZES_KB = [0, 2, 8, 32, 128, 64]

    def __init__(self, header_bytes: bytes):
        if len(header_bytes) != 0x50:
            raise ValueError("Cartridge header must be 80 bytes long")
        self.bin = header_bytes

    @property
    def main_offset(self):
        jump = 0xc3
        if self.bin[1] == jump:
            addr = self.bin[2:4]
        elif self.bin[0] == jump:
            addr = self.bin[1:3]
        else:
            return None
        return Address.from_rom_offset(int.from_bytes(addr, 'little'))

    @property
    def title(self) -> str:
        end = 0x43 if self.bin[0x43] >= 0x80 else 0x44
        return self.bin[52:end].decode('ascii').strip('\x00')

    @property
    def cgb_flag(self):
        flag = self.bin[0x43]
        if flag < 0x80:
            return 'dmg'
        elif flag == 0x80:
            return 'both'
        elif flag == 0xc0:
            return 'cgb'
        else:
            return '?'

    @property
    def sgb_flag(self):
        return self.bin[0x46] == 3

    @property
    def rom_banks(self):
        return self.ROM_BANKS[self.bin[0x48]]

    @property
    def sram_size_kb(self):
        return self.SRAM_SIZES_KB[self.bin[0x49]]
