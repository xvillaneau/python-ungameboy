from dataclasses import dataclass
from typing import BinaryIO, Optional, List, NamedTuple, Union

from .address import Address, ROM
from .binary_data import DataBlock, DataManager
from .context import ContextManager
from .data_types import Byte, IORef, Ref, Word
from .decoder import ROMBytes
from .enums import Operation as Op
from .instructions import RawInstruction
from .labels import LabelManager, Label
from .sections import SectionManager, Section


class Disassembler:
    """
    The disassembler is where all the data is combined into a single
    record for each address.
    """
    def __init__(self):
        self.rom: Optional[ROMBytes] = None
        self.rom_path = None
        self.project_name = ""

        self.data = DataManager(self)
        self.context = ContextManager()
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

    def __getitem__(self, addr) -> "AsmElement":
        if self.rom is None:
            raise ValueError("No ROM loaded")
        if not isinstance(addr, Address):
            raise TypeError()

        labels = self.labels.get_labels(addr)
        section = self.sections.get_section(addr)

        scope = self.labels.scope_at(addr)
        scope_name = scope[1][-1] if scope is not None else ''

        data = self.data.get_data(addr)
        if data is not None:
            offset = addr.offset - data.address.offset
            row_n = offset // data.row_size
            row = data.get_row_bin(row_n)

            return DataRow(
                address=data.address + row_n * data.row_size,
                size=len(row),
                labels=labels,
                scope=scope_name,
                section_start=section,
                bytes=row,
                data_block=data,
                row=row_n,
            )

        elif addr.type is ROM:
            raw_instr = self.rom.decode_instruction(addr.rom_file_offset)
            context = self.get_context(raw_instr)

            return Instruction(
                address=raw_instr.address,
                size=raw_instr.length,
                labels=labels,
                scope=scope_name,
                section_start=section,
                bytes=raw_instr.bytes,
                raw_instruction=raw_instr,
                context=context,
            )

        raise ValueError()

    def get_context(self, instr: RawInstruction) -> "InstructionContext":

        if instr.value_pos <= 0:
            return NO_CONTEXT

        arg = instr.args[instr.value_pos - 1]
        if isinstance(arg, Word):
            value = Address.from_memory_address(arg)
        elif instr.type is Op.RelJump:
            value = instr.next_address + arg
        elif isinstance(arg, IORef) and isinstance(arg.target, Byte):
            value = Address.from_memory_address(arg.target + 0xff00)
        elif isinstance(arg, Ref) and isinstance(arg.target, Word):
            value = Address.from_memory_address(arg.target)
        else:
            return NO_CONTEXT

        # Auto-detect ROM bank if current instruction requires one
        if value.bank < 0:
            if value.type is ROM and instr.address.bank > 0:
                bank = instr.address.bank
            else:
                bank = self.context.bank_override.get(instr.address, -1)
            if bank >= 0:
                value = Address(value.type, bank, value.offset)

        if instr.type is Op.Load and instr.value_pos == 1:
            value = detect_special_label(value)
        if not isinstance(value, SpecialLabel):
            dest_labels = self.labels.get_labels(value) or [value]
            value = dest_labels[-1]

        return InstructionContext(
            value_symbol=value,
            force_scalar=instr.address in self.context.force_scalar,
        )


class SpecialLabel(NamedTuple):
    name: str


def detect_special_label(address: Address) -> Union[SpecialLabel, Address]:
    if address.type is not ROM:
        return address
    offset = address.memory_address
    if offset < 0x2000:
        return SpecialLabel("SRAM_ENABLE")
    if offset < 0x3000:
        return SpecialLabel("ROM_BANK_L")
    if offset < 0x4000:
        return SpecialLabel("ROM_BANK_9")
    if offset < 0x6000:
        return SpecialLabel("SRAM_BANK")
    return address


@dataclass(frozen=True)
class InstructionContext:
    value_symbol: Union[None, Address, Label, SpecialLabel] = None
    force_scalar: bool = False


NO_CONTEXT = InstructionContext()


@dataclass
class AsmElement:
    address: Address
    size: int

    labels: List[Label]
    scope: str
    section_start: Optional[Section]

    @property
    def next_address(self):
        return self.address + self.size


@dataclass
class RomElement(AsmElement):
    bytes: bytes


@dataclass
class Instruction(RomElement):
    raw_instruction: RawInstruction
    context: InstructionContext


@dataclass
class DataRow(RomElement):
    data_block: DataBlock
    row: int


@dataclass
class EmptyROM(AsmElement):
    pass


@dataclass
class Register(AsmElement):
    pass
