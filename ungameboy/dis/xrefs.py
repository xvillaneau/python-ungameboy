from typing import TYPE_CHECKING, NamedTuple, Optional, Set

from .labels import Label
from .models import Instruction
from ..address import Address
from ..data_structures import AddressMapping
from ..enums import Operation as Op

if TYPE_CHECKING:
    from .disassembler import Disassembler


class XRefs(NamedTuple):
    address: Address
    called_by: Set[Address]
    calls: Optional[Address]


class XRefManager:
    def __init__(self, disassembler: "Disassembler"):
        self.asm = disassembler

        self._calls_to: AddressMapping[Address] = AddressMapping()
        self._calls_from: AddressMapping[Set[Address]] = AddressMapping()

    def auto_declare(self, address: Address):
        elem = self.asm[address]
        if isinstance(elem, Instruction):
            if isinstance(elem.value, Label):
                target = elem.value.address
            elif isinstance(elem.value, Address):
                target = elem.value
            else:
                return
            if elem.raw_instruction.type in (Op.Call, Op.Vector):
                self.declare_call(elem.address, target)

    def declare_call(self, addr_from: Address, addr_to: Address):
        if addr_from in self._calls_to:
            current_to = self._calls_to[addr_from]
            self._calls_from[current_to].remove(addr_from)
            if not self._calls_from[current_to]:
                del self._calls_from[current_to]

        self._calls_to[addr_from] = addr_to
        self._calls_from.setdefault(addr_to, set()).add(addr_from)

    def get_xrefs(self, address: Address) -> XRefs:
        called_by = self._calls_from.get(address, set())
        calls = self._calls_to.get(address)
        return XRefs(address, called_by, calls)

    def save_items(self):
        for _from, _to in self._calls_to.items():
            yield ('xref', 'declare', 'call', _from, _to)
