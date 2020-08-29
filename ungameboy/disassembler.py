from dataclasses import dataclass
from typing import BinaryIO, Optional, List, NamedTuple, Union

from .address import Address, ROM
from .binary_data import DataBlock, DataManager, RowItem
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
            row_bin = data.get_row_bin(row_n)
            row_addr = data.address + row_n * data.row_size

            row_values = [
                (
                    self.addr_context(row_addr, item)
                    if isinstance(item, Address)
                    else item
                )
                for item in data[row_n]
            ]

            return DataRow(
                address=row_addr,
                size=len(row_bin),
                labels=labels,
                scope=scope_name,
                section_start=section,
                bytes=row_bin,
                data_block=data,
                values=row_values,
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
            target = Address.from_memory_address(arg)
        elif instr.type is Op.RelJump:
            target = instr.next_address + arg
        elif isinstance(arg, IORef) and isinstance(arg.target, Byte):
            target = Address.from_memory_address(arg.target + 0xff00)
        elif isinstance(arg, Ref) and isinstance(arg.target, Word):
            target = Address.from_memory_address(arg.target)
        else:
            return NO_CONTEXT

        value = self.addr_context(instr.address, target)

        if instr.type is Op.Load and instr.value_pos == 1:
            special = detect_special_label(target)
            if isinstance(special, SpecialLabel):
                value = special

        return InstructionContext(
            value_symbol=value,
            force_scalar=instr.address in self.context.force_scalar,
        )

    def addr_context(self, current: Address, target: Address):
        # Auto-detect ROM bank if current instruction requires one
        if target.bank < 0:
            if target.type is ROM and current.bank > 0:
                bank = current.bank
            else:
                bank = self.context.bank_override.get(current, -1)
            if bank >= 0:
                target = Address(target.type, bank, target.offset)

        # Detect labels
        target_labels = self.labels.get_labels(target) or [target]
        return target_labels[-1]


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
    values: List[Union[RowItem, Label]]
    row: int


@dataclass
class EmptyROM(AsmElement):
    pass


@dataclass
class Register(AsmElement):
    pass
