from datetime import datetime, timezone
from typing import BinaryIO, List, Optional

from .binary_data import BinaryData, DataManager
from .comments import CommentsManager
from .context import ContextManager
from .decoder import ROMBytes
from .labels import LabelManager
from .manager_base import AsmManager
from .models import AsmElement, Instruction, DataBlock, DataRow, RamElement
from .sections import SectionManager
from .xrefs import XRefManager
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
        self.last_save = datetime.now(timezone.utc)

        self.data = DataManager(self)
        self.comments = CommentsManager(self)
        self.context = ContextManager(self)
        self.labels = LabelManager(self)
        self.sections = SectionManager()
        self.xrefs = XRefManager(self)

        self.managers: List[AsmManager] = [
            self.data, self.labels, self.xrefs, self.context, self.comments
        ]

    @property
    def is_loaded(self):
        return self.rom is not None

    def reset(self):
        for manager in self.managers:
            manager.reset()

    def load_rom(self, rom_file: BinaryIO):
        if hasattr(rom_file, 'name'):
            self.rom_path = rom_file.name
        self.rom = ROMBytes(rom_file)

    def __getitem__(self, addr) -> AsmElement:
        if self.rom is None:
            raise ValueError("No ROM loaded")
        if not isinstance(addr, Address):
            raise TypeError()

        scope = self.labels.scope_at(addr)
        common_args = {
            "labels": self.labels.get_labels(addr),
            "section": self.sections.get_section(addr),
            "xrefs": self.xrefs.get_xrefs(addr),
            "scope": scope[-1] if scope else None,
            "comment": self.comments.inline.get(addr, ""),
            "block_comment": self.comments.blocks.get(addr, []),
        }

        data = self.data.get_data(addr)
        if isinstance(data, BinaryData):
            offset = addr.offset - data.address.offset
            row_n = offset // data.row_size
            row_bin = data.get_row_bin(row_n)
            row_addr = data.address + row_n * data.row_size
            row = data[row_n]
            row_values, dest_address = self.context.row_context(row, row_addr)

            return DataRow(
                address=row_addr,
                size=len(row_bin),
                dest_address=dest_address,
                **common_args,
                bytes=row_bin,
                data=data,
                values=row_values,
                row=row_n,
            )

        elif data is not None:
            return DataBlock(
                address=addr,
                size=data.size,
                dest_address=None,
                **common_args,
                bytes=data.bytes,
                data=data,
            )

        elif addr.type is ROM:
            raw_instr = self.rom.decode_instruction(addr.rom_file_offset)
            value, dest_address = self.context.instruction_context(raw_instr)

            return Instruction(
                address=raw_instr.address,
                size=raw_instr.length,
                dest_address=dest_address,
                **common_args,
                bytes=raw_instr.bytes,
                raw_instruction=raw_instr,
                value=value,
            )

        # VRAM/SRAM/WRAM/HRAM
        return RamElement(
            address=addr,
            size=1,
            **common_args,
        )
