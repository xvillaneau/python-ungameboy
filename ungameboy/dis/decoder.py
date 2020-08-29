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
