from typing import TYPE_CHECKING, NamedTuple, Optional, Set, Tuple

from .labels import Label
from .models import Instruction
from ..address import Address
from ..data_structures import AddressMapping
from ..enums import Operation as Op

if TYPE_CHECKING:
    from .disassembler import Disassembler


class XRefs(NamedTuple):
    address: Address
    calls: Optional[Address]
    called_by: Set[Address]
    jumps_to: Optional[Address]
    jumps_from: Set[Address]
    reads: Optional[Address]
    read_by: Set[Address]
    writes_to: Optional[Address]
    written_by: Set[Address]


class LinksCollection:
    def __init__(self):
        self.links_to: AddressMapping[Address] = AddressMapping()
        self.links_from: AddressMapping[Set[Address]] = AddressMapping()

    def items(self):
        return self.links_to.items()

    def create_link(self, addr_from: Address, addr_to: Address):
        if addr_from in self.links_to:
            current_to = self.links_to[addr_from]
            self.remove_link(addr_from, current_to)

        self.links_to[addr_from] = addr_to
        self.links_from.setdefault(addr_to, set()).add(addr_from)

    def remove_link(self, addr_from: Address, addr_to: Address):
        if addr_from in self.links_from.get(addr_to, ()):
            self.links_from[addr_to].remove(addr_from)
            if not self.links_from[addr_to]:
                del self.links_from[addr_to]
        if addr_from in self.links_to:
            self.links_to.pop(addr_from)

    def clear(self, address: Address):
        if address in self.links_to:
            self.remove_link(address, self.links_to[address])
        if address in self.links_from:
            for origin in list(self.links_from[address]):
                self.remove_link(origin, address)

    def get_links(self, address: Address) -> Tuple[Optional[Address], Set[Address]]:
        return self.links_to.get(address), self.links_from.get(address, set())


class XRefManager:
    def __init__(self, disassembler: "Disassembler"):
        self.asm = disassembler

        self._mappings = {
            'call': LinksCollection(),
            'jump': LinksCollection(),
            'read': LinksCollection(),
            'write': LinksCollection(),
        }

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
                self.declare('call', elem.address, target)
            elif op in (Op.AbsJump, Op.RelJump):
                self.declare('jump', elem.address, target)

    def declare(self, link_type: str, addr_from: Address, addr_to: Address):
        self._mappings[link_type].create_link(addr_from, addr_to)

    def clear(self, address: Address):
        for links in self._mappings.values():
            links.clear(address)

    def get_xrefs(self, address: Address) -> XRefs:
        return XRefs(
            address,
            *(
                arg
                for links in self._mappings.values()
                for arg in links.get_links(address)
            )
        )

    def save_items(self):
        for _type, _links in self._mappings.items():
            for _from, _to in _links.items():
                yield ('xref', 'declare', _type, _from, _to)
