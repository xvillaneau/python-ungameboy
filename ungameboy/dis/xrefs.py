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

    def _get_mappings(self, link_type):
        if link_type == 'call':
            return self._calls_from, self._calls_to
        if link_type == 'jump':
            return self._jumps_from, self._jumps_to
        raise ValueError(link_type)

    def _declare_link(self, link_type, addr_from, addr_to):
        links_from, links_to = self._get_mappings(link_type)
        if addr_from in links_to:
            current_to = links_to[addr_from]
            self._remove_link(link_type, addr_from, current_to)

        links_to[addr_from] = addr_to
        links_from.setdefault(addr_to, set()).add(addr_from)

    def _remove_link(self, link_type, addr_from: Address, addr_to: Address):
        links_from, links_to = self._get_mappings(link_type)

        if addr_from in links_from.get(addr_to, ()):
            links_from[addr_to].remove(addr_from)
            if not links_from[addr_to]:
                del links_from[addr_to]
        if addr_to in links_to:
            links_to.pop(addr_to)

    def declare_call(self, addr_from: Address, addr_to: Address):
        self._declare_link('call', addr_from, addr_to)

    def declare_jump(self, addr_from: Address, addr_to: Address):
        self._declare_link('jump', addr_from, addr_to)

    def clear(self, address: Address):
        if address in self._calls_to:
            self._remove_link('call', address, self._calls_to[address])
        if address in self._calls_from:
            for origin in list(self._calls_from[address]):
                self._remove_link('call', origin, address)
        if address in self._jumps_to:
            self._remove_link('jump', address, self._jumps_to[address])
        if address in self._jumps_from:
            for origin in list(self._jumps_from[address]):
                self._remove_link('jump', origin, address)

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
