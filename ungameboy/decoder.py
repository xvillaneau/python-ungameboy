from .models import Op
from .instructions import CODE_POINTS, Instruction

__all__ = ['ROMBytes', 'Decoder']


class ROMBytes:
    """
    Represents the raw ROM file. It's entirely stored in memory, though
    this object should be used to
    """

    def __init__(self, rom_path):
        # Just store the entire ROM in memory
        with open(rom_path, 'rb') as rom_file:
            self.rom = rom_file.read()

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

    def decode_instruction(self, index: int) -> Instruction:
        """
        Decode the instruction for which the code is at a given address.
        This may read more than one byte, or return invalid data.
        """
        op = CODE_POINTS[self.rom[index]]

        if op.length == 1:
            parameters = b''

        else:  # length >= 2
            parameters = bytes(self.rom[index + 1:index + op.length])

            if len(parameters) + 1 != op.length:
                binary = bytes(self.rom[index:index + op.length])
                return Instruction(
                    Op.Invalid, (), index, len(binary), binary
                )

        return op.make_instance(index, parameters)

    def __iter__(self):
        return self

    def __next__(self) -> Instruction:
        if self.index >= self.stop:
            raise StopIteration()
        instr = self.decode_instruction(self.index)
        self.index += instr.length
        return instr

    def seek(self, index: int):
        if not 0 <= index < self.stop:
            raise IndexError("Index out of bounds")
        self.index = index
