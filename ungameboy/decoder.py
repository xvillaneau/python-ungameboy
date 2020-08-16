from .address import Address
from .models import Op
from .instructions import CODE_POINTS, Instruction

__all__ = ['ROMBytes']


class ROMBytes:
    """
    Represents the raw ROM file. It's entirely stored in memory, though
    this object should be used to
    """

    def __init__(self, rom_file):
        # Just store the entire ROM in memory
        self.rom = rom_file.read()

    @classmethod
    def from_path(cls, rom_path):
        with open(rom_path, 'rb') as rom_file:
            return cls(rom_file)

    def __len__(self):
        return len(self.rom)

    def __getitem__(self, item):
        return self.rom[item]

    def decode(self, start=None, stop=None) -> "Decoder":
        if start is None:
            start = 0
        elif not 0 <= start < len(self.rom):
            raise IndexError("Decoding must start at a valid position")
        if stop is not None and stop < start:
            raise IndexError("Decoding cannot stop before its start")
        return Decoder(self, start, stop)

    def decode_instruction(self, offset: int) -> Instruction:
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
                return Instruction(
                    Op.Invalid, (), addr, len(binary), binary
                )

        return op.make_instance(addr, parameters)


class Decoder:
    """
    A Decoder instance is a stateful iterator that yields instructions

    The decoder's role is to convert a stream of bytes into a sequence
    of CPU instructions. If it runs into bytes that it cannot decode,
    then it will return an "invalid" instruction and move on.
    """

    def __init__(self, rom: ROMBytes, start: int = 0, stop: int = None):
        self.rom = rom
        self.index = start

        if stop is None:
            self.stop = len(rom)
        else:
            self.stop = min(stop, len(rom))

    def __iter__(self):
        return self

    def __next__(self) -> Instruction:
        if self.index >= self.stop:
            raise StopIteration()
        instr = self.rom.decode_instruction(self.index)
        self.index += instr.length
        return instr
