from dataclasses import dataclass
from typing import Union

from .data_block import DataBlock, DataManager
from .decoder import Decoder, ROMBytes
from .instructions import Instruction


@dataclass
class AsmData:
    binary: Union[DataBlock, Instruction]

    @property
    def address(self):
        return self.binary.address

    @property
    def next_address(self):
        return self.binary.next_address


class Disassembler:
    def __init__(self, rom: ROMBytes):
        self.rom = rom
        self.data = DataManager()

        self._decoder = Decoder(self.rom)

    def __len__(self):
        return len(self.rom)

    def __iter__(self):
        return AssemblyView(self)

    def __getitem__(self, item):
        if isinstance(item, slice):
            if item.step not in (None, 1):
                raise IndexError("Can only query assembly in steps of 1")
            start, stop, _ = item.indices(len(self.rom))
            return AssemblyView(self, start, stop)

        if not isinstance(item, int):
            raise TypeError()

        data = self.data.get_data(item)
        if data is not None:
            binary = data
        else:
            binary = self._decoder.decode_instruction(item)
        return AsmData(binary)


class AssemblyView:
    def __init__(self, asm: Disassembler, start: int = 0, stop: int = None):
        self.asm = asm
        self.decoder = Decoder(self.asm.rom)

        self.address = start
        if stop is None:
            self.stop = len(asm.rom)
        else:
            self.stop = min(stop, len(asm.rom))

    def __iter__(self):
        return self

    def __next__(self):
        if self.address >= self.stop:
            raise StopIteration()
        data: AsmData = self.asm[self.address]
        self.address = data.binary.next_address
        return data
