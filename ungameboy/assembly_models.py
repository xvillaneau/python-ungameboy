from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Union

from .address import Address
from .instructions import RawInstruction
from .labels import Label


class ElementType(str, Enum):
    ROMElement = "ROM"
    RAMElement = "RAM"


@dataclass
class AsmElement:
    address: Address
    size: int

    labels: List[Label]

    @property
    def next_address(self):
        return self.address + self.size


@dataclass
class Instruction(AsmElement):
    raw_instruction: RawInstruction
    value_symbol: Optional[Union[Address, Label]] = None
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
