from dataclasses import dataclass
from typing import BinaryIO, Optional, List, NamedTuple, Union

from .address import Address, ROM
from .data_block import DataManager
from .data_types import Byte, IORef, Ref, Word
from .decoder import ROMBytes
from .enums import Operation as Op
from .instructions import RawInstruction
from .labels import LabelManager, Label
from .sections import SectionManager, Section

__all__ = ['AsmElement', 'DataBlock', 'Disassembler', 'Instruction', 'SpecialLabel']


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
        self.sections = SectionManager()

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

    def __getitem__(self, item) -> "AsmElement":
        if self.rom is None:
            raise ValueError("No ROM loaded")
        if not isinstance(item, Address):
            raise TypeError()

        labels = self.labels.get_labels(item)
        section = self.sections.get_section(item)

        data = self.data.get_data(item)
        if data is not None:
            return DataBlock(
                address=data.address,
                size=data.length,
                labels=labels,
                section_start=section,
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
                # Auto-detect ROM bank if current instruction requires one
                if addr.type == item.type == ROM and addr.bank < 0 < item.bank:
                    value = addr = Address(ROM, item.bank, addr.offset)

                dest_labels = self.labels.get_labels(addr)
                if dest_labels:
                    value = dest_labels[-1]

                if raw_instr.type is Op.Load and raw_instr.value_pos == 1:
                    special = detect_special_label(addr)
                    if special is not None:
                        value = special

            scope = self.labels.scope_at(item)
            if scope is not None:
                scope_name = scope[1][-1]
            else:
                scope_name = ''

            return Instruction(
                address=raw_instr.address,
                size=raw_instr.length,
                labels=labels,
                section_start=section,
                raw_instruction=raw_instr,
                value_symbol=value,
                scope=scope_name,
            )

        raise ValueError()


class SpecialLabel(NamedTuple):
    name: str


def detect_special_label(address: Address):
    if address.type is not ROM:
        return None
    offset = address.memory_address
    if offset < 0x2000:
        return SpecialLabel("SRAM_ENABLE")
    if offset < 0x3000:
        return SpecialLabel("ROM_BANK_L")
    if offset < 0x4000:
        return SpecialLabel("ROM_BANK_9")
    if offset < 0x6000:
        return SpecialLabel("SRAM_BANK")
    return None


@dataclass
class AsmElement:
    address: Address
    size: int

    labels: List[Label]
    section_start: Optional[Section]

    @property
    def next_address(self):
        return self.address + self.size


@dataclass
class Instruction(AsmElement):
    raw_instruction: RawInstruction
    value_symbol: Optional[Union[Address, Label, SpecialLabel]] = None
    scope: str = ''


@dataclass
class DataBlock(AsmElement):
    name: str


@dataclass
class EmptyROM(AsmElement):
    pass


@dataclass
class Register(AsmElement):
    pass
