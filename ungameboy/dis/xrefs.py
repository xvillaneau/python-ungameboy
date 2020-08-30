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
    jumps_from: Set[Address]
    jumps_to: Optional[Address]


class XRefManager:
    def __init__(self, disassembler: "Disassembler"):
        self.asm = disassembler

        self._calls_to: AddressMapping[Address] = AddressMapping()
        self._calls_from: AddressMapping[Set[Address]] = AddressMapping()
        self._jumps_to: AddressMapping[Address] = AddressMapping()
        self._jumps_from: AddressMapping[Set[Address]] = AddressMapping()

    def auto_declare(self, address: Address):
        elem = self.asm[address]
        if isinstance(elem, Instruction):
            if isinstance(elem.value, Label):
                target = elem.value.address
            elif isinstance(elem.value, Address):
                target = elem.value
            else:
                return
            op = elem.raw_instruction.type
            if op in (Op.Call, Op.Vector):
                self.declare_call(elem.address, target)
            elif op in (Op.AbsJump, Op.RelJump):
                self.declare_jump(elem.address, target)

    @classmethod
    def _declare_link(cls, addr_from, addr_to, links_from, links_to):
        if addr_from in links_to:
            current_to = links_to[addr_from]
            links_from[current_to].remove(addr_from)
            if not links_from[current_to]:
                del links_from[current_to]

        links_to[addr_from] = addr_to
        links_from.setdefault(addr_to, set()).add(addr_from)

    def declare_call(self, addr_from: Address, addr_to: Address):
        self._declare_link(addr_from, addr_to, self._calls_from, self._calls_to)

    def declare_jump(self, addr_from: Address, addr_to: Address):
        self._declare_link(addr_from, addr_to, self._jumps_from, self._jumps_to)

    def get_xrefs(self, address: Address) -> XRefs:
        return XRefs(
            address,
            self._calls_from.get(address, set()),
            self._calls_to.get(address),
            self._jumps_from.get(address, set()),
            self._jumps_to.get(address),
        )

    def save_items(self):
        for _from, _to in self._calls_to.items():
            yield ('xref', 'declare', 'call', _from, _to)
        for _from, _to in self._jumps_to.items():
            yield ('xref', 'declare', 'jump', _from, _to)
