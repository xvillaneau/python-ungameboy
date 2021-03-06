from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Union

from .labels import Label, LabelOffset
from .special_labels import SpecialLabel
from ..address import Address

if TYPE_CHECKING:
    from .data import Data
    from .instructions import RawInstruction
    from .sections import Section
    from .xrefs import XRefs

__all__ = [
    'AsmElement', 'RamElement', 'RomElement', 'DataBlock', 'DataRow',
    'Instruction', 'Value'
]

Value = Union[int, str, Address, Label, LabelOffset, SpecialLabel]


@dataclass
class AsmElement:
    address: Address
    size: int

    labels: List[Label]
    scope: Optional[Label]
    section: Optional['Section']
    xrefs: 'XRefs'
    comment: str
    block_comment: List[str]

    @property
    def next_address(self):
        return self.address + self.size


@dataclass
class RomElement(AsmElement):
    dest_address: Optional[Address]
    bytes: bytes


@dataclass
class Instruction(RomElement):
    raw_instruction: 'RawInstruction'
    value: Value


@dataclass
class DataRow(RomElement):
    data: 'Data'
    values: List[Value]
    row: int


@dataclass
class DataBlock(RomElement):
    data: 'Data'


@dataclass
class RamElement(AsmElement):
    pass
