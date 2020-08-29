from typing import BinaryIO, Optional

from .binary_data import DataManager
from .context import ContextManager
from .decoder import ROMBytes
from .labels import LabelManager
from .models import AsmElement, Instruction, DataRow
from .sections import SectionManager
from ..address import Address, ROM

__all__ = ['Disassembler']


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
        self.context = ContextManager(self)
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

    def __getitem__(self, addr) -> AsmElement:
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
                    self.context.address_context(row_addr, item)
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
            value = self.context.instruction_context(raw_instr)

            return Instruction(
                address=raw_instr.address,
                size=raw_instr.length,
                labels=labels,
                scope=scope_name,
                section_start=section,
                bytes=raw_instr.bytes,
                raw_instruction=raw_instr,
                value=value,
            )

        raise ValueError()
