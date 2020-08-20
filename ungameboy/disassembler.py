from abc import ABCMeta, abstractmethod
from typing import BinaryIO, NamedTuple, Optional

from .address import Address, ROM
from .assembly_models import AsmElement, DataBlock, Instruction
from .data_block import DataManager
from .data_types import Byte, IORef, Ref, Word
from .decoder import ROMBytes
from .enums import Operation as Op
from .labels import LabelManager

__all__ = ['AssemblyView', 'Disassembler', 'ROMView', 'ViewItem']


class Disassembler:
    """
    The disassembler is where all the data is combined into a single
    record for each address.
    """
    def __init__(self):
        self.rom: Optional[ROMBytes] = None
        self.rom_path = None
        self.project_name = ""

        self.data = DataManager()
        self.labels = LabelManager()

    @property
    def is_loaded(self):
        return self.rom is not None

    def reset(self):
        proj_name = self.project_name
        self.__init__()
        self.project_name = proj_name

    def load_rom(self, rom_file: BinaryIO):
        if hasattr(rom_file, 'name'):
            self.rom_path = rom_file.name
        self.rom = ROMBytes(rom_file)

    def __getitem__(self, item) -> AsmElement:
        if self.rom is None:
            raise ValueError("No ROM loaded")
        if not isinstance(item, Address):
            raise TypeError()

        labels = self.labels.labels_at(item)

        data = self.data.get_data(item)
        if data is not None:
            return DataBlock(
                address=data.address,
                size=data.length,
                labels=labels,
                name=data.description
            )

        elif item.type is ROM:
            raw_instr = self.rom.decode_instruction(item.rom_file_offset)
            addr = None

            if raw_instr.value_pos > 0:
                arg = raw_instr.args[raw_instr.value_pos - 1]
                if raw_instr.type in [Op.AbsJump, Op.Call]:
                    addr = Address.from_memory_address(arg)
                elif raw_instr.type is Op.RelJump:
                    addr = raw_instr.next_address + arg
                elif isinstance(arg, IORef) and isinstance(arg.target, Byte):
                    addr = Address.from_memory_address(arg.target + 0xff00)
                elif isinstance(arg, Ref) and isinstance(arg.target, Word):
                    addr = Address.from_memory_address(arg.target)

            value = addr
            if addr is not None:
                dest_labels = self.labels.labels_at(addr)
                if dest_labels:
                    value = dest_labels[0]

            return Instruction(
                address=raw_instr.address,
                size=raw_instr.length,
                labels=labels,
                raw_instruction=raw_instr,
                value_symbol=value,
            )

        raise ValueError()


class ViewItem(NamedTuple):
    item_index: int
    data: AsmElement

    @property
    def next_index(self):
        return self.item_index + self.data.size


class AssemblyView(metaclass=ABCMeta):
    """
    Abstract base class for other "Assembly View" classes.

    An "Assembly View" is a linear representation of a section of the
    global address space. It is linear in the sense that it can be
    queried with an index and handles converting that index into a
    global address that the disassembler can understand. This allows
    client classes (the buffer, mainly) to not need to worry about
    doing arithmetics with addresses.
    """
    def __init__(self, asm: Disassembler, start: int = 0):
        self.asm = asm
        self.index = start

    @classmethod
    @abstractmethod
    def index_to_address(cls, index: int) -> Address:
        pass

    @classmethod
    @abstractmethod
    def address_to_index(cls, address: Address) -> Optional[int]:
        pass

    @property
    @abstractmethod
    def end(self) -> int:
        pass

    def __len__(self):
        return self.end

    def seek(self, index: int):
        self.index = index

    def __getitem__(self, item):
        if not self.asm.is_loaded:
            raise ValueError
        if isinstance(item, slice):
            return self.__class__(self.asm, item.start or 0)
        elif not isinstance(item, int):
            raise TypeError()
        return self.asm[self.index_to_address(item)]

    def __iter__(self):
        return self

    def __next__(self) -> ViewItem:
        if self.index >= len(self):
            raise StopIteration()
        data = self[self.index]
        item = ViewItem(self.index, data)
        self.index += data.size
        return item


class ROMView(AssemblyView):
    """View that only includes the ROM"""
    @classmethod
    def index_to_address(cls, index: int) -> Address:
        return Address.from_rom_offset(index)

    @classmethod
    def address_to_index(cls, address: Address) -> Optional[int]:
        if address.type is not ROM:
            return None
        return address.rom_file_offset

    @property
    def end(self):
        return len(self.asm.rom)
