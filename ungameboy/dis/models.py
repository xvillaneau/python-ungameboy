from dataclasses import dataclass
from typing import TYPE_CHECKING, List, Optional, Union

from .labels import Label
from .special_labels import SpecialLabel
from ..address import Address

if TYPE_CHECKING:
    from .binary_data import DataBlock
    from .instructions import RawInstruction
    from .sections import Section
    from .xrefs import XRefs

__all__ = ['AsmElement', 'RomElement', 'DataRow', 'Instruction', 'Value']

Value = Union[int, Address, Label, SpecialLabel]


@dataclass
class AsmElement:
    address: Address
    size: int

    labels: List[Label]
    scope: str
    section: Optional['Section']
    xrefs: Optional['XRefs']

    @property
    def next_address(self):
        return self.address + self.size


@dataclass
class RomElement(AsmElement):
    bytes: bytes


@dataclass
class Instruction(RomElement):
    raw_instruction: 'RawInstruction'
    value: Value


@dataclass
class DataRow(RomElement):
    data_block: 'DataBlock'
    values: List[Value]
    row: int