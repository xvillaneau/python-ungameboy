from datetime import datetime, timezone
from typing import BinaryIO, List, Optional

from .analysis import AnalysisManager
from .comments import CommentsManager
from .context import ContextManager
from .data import DataManager, CartridgeHeader, EmptyData
from .decoder import HeaderDecoder, ROMBytes
from .labels import LabelManager
from .manager_base import AsmManager
from .models import AsmElement, Instruction, DataBlock, DataRow, RamElement
from .sections import SectionManager
from .xrefs import XRefManager
from ..address import Address, ROM
from ..commands import LabelName
from ..scripts import ScriptsManager

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

        self.analyze = AnalysisManager(self)
        self.data = DataManager(self)
        self.comments = CommentsManager(self)
        self.context = ContextManager(self)
        self.labels = LabelManager(self)
        self.scripts = ScriptsManager(self)
        self.sections = SectionManager()
        self.xrefs = XRefManager(self)

        self.managers: List[AsmManager] = [
            self.data, self.labels, self.xrefs, self.context, self.comments,
            self.analyze, self.scripts,
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

    def setup_new_rom(self):
        if not self.is_loaded:
            return

        entry_point = Address.from_rom_offset(0x100)
        if not self.labels.get_labels(entry_point):
            self.labels.create(entry_point, LabelName("entry_point"))

        header_start = entry_point + 4
        if not self.data.get_data(header_start):
            self.data.create_header()

        header = self.data.get_data(header_start)
        if not isinstance(header, CartridgeHeader):
            return

        main = HeaderDecoder(header.data).main_offset
        if main is not None and not self.labels.get_labels(main):
            self.labels.create(main, LabelName("main"))

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
        if data is not None:

            if isinstance(data, (CartridgeHeader, EmptyData)):
                return DataBlock(
                    address=addr,
                    size=data.size,
                    dest_address=None,
                    **common_args,
                    bytes=data.rom_bytes,
                    data=data,
                )

            row = data[addr]
            row_values, dest_address = self.context.row_context(row)

            return DataRow(
                address=row.address,
                size=len(row.bytes),
                dest_address=dest_address,
                **common_args,
                bytes=row.bytes,
                data=data,
                values=row_values,
                row=row.num,
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
