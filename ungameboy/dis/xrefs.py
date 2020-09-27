from typing import TYPE_CHECKING, NamedTuple, Optional, Set, Tuple

import click

from .manager_base import AsmManager
from .models import DataRow, Instruction
from ..address import Address
from ..commands import AddressOrLabel, UgbCommandGroup
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

    def reset(self):
        self.links_to.clear()
        self.links_from.clear()

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


class XRefManager(AsmManager):
    def __init__(self, disassembler: "Disassembler"):
        super().__init__(disassembler)

        self._mappings = {
            'call': LinksCollection(),
            'jump': LinksCollection(),
            'read': LinksCollection(),
            'write': LinksCollection(),
        }

    def reset(self) -> None:
        for collection in self._mappings.values():
            collection.reset()

    def auto_declare(self, address: Address):
        elem = self.asm[address]
        if isinstance(elem, Instruction):
            if elem.dest_address is None:
                return

            op = elem.raw_instruction.type
            declare = ''
            if op in (Op.Call, Op.Vector):
                declare = 'call'
            elif op in (Op.AbsJump, Op.RelJump):
                declare = 'jump'
            elif op in (Op.Load, Op.LoadFast):
                declare = ('', 'write', 'read')[elem.raw_instruction.value_pos]

            if declare:
                self.declare(declare, elem.address, elem.dest_address)

        elif isinstance(elem, DataRow):
            if elem.dest_address is not None:
                self.declare('jump', elem.address, elem.dest_address)

    def declare(self, link_type: str, addr_from: Address, addr_to: Address):
        self._mappings[link_type].create_link(addr_from, addr_to)

    def clear(self, address: Address):
        for links in self._mappings.values():
            links.clear(address)

    def count_incoming(self, link_type: str, address: Address):
        links = self._mappings[link_type].links_from
        return len(links.get(address, ()))

    def get_xrefs(self, address: Address) -> XRefs:
        return XRefs(
            address,
            *(
                arg
                for links in self._mappings.values()
                for arg in links.get_links(address)
            )
        )

    def build_cli(self) -> 'click.Command':
        xref_cli = click.Group('xref')
        address_arg = AddressOrLabel(self.asm)

        @xref_cli.command('auto')
        @click.argument("address", type=address_arg)
        def xref_auto_detect(address: Address):
            self.auto_declare(address)

        @xref_cli.command('clear')
        @click.argument("address", type=address_arg)
        def xref_clear(address: Address):
            self.clear(address)

        @xref_cli.group('declare')
        def xref_declare():
            pass

        @xref_declare.command('call')
        @click.argument("addr_from", type=address_arg)
        @click.argument("addr_to", type=address_arg)
        def xref_declare_call(addr_from, addr_to):
            self.declare('call', addr_from, addr_to)

        @xref_declare.command('jump')
        @click.argument("addr_from", type=address_arg)
        @click.argument("addr_to", type=address_arg)
        def xref_declare_jump(addr_from, addr_to):
            self.declare('jump', addr_from, addr_to)

        @xref_declare.command('read')
        @click.argument("addr_from", type=address_arg)
        @click.argument("addr_to", type=address_arg)
        def xref_declare_read(addr_from, addr_to):
            self.declare('read', addr_from, addr_to)
            return False

        @xref_declare.command('write')
        @click.argument("addr_from", type=address_arg)
        @click.argument("addr_to", type=address_arg)
        def xref_declare_write(addr_from, addr_to):
            self.declare('write', addr_from, addr_to)
            return False

        return xref_cli

    def build_cli_v2(self) -> 'UgbCommandGroup':
        def make_declare(link_type: str):
            def declare(addr_from: Address, addr_to: Address):
                self.declare(link_type, addr_from, addr_to)
            return declare

        declare_cli = UgbCommandGroup(self.asm, "declare")
        for name in self._mappings:
            declare_cli.add_command(name, make_declare(name))

        xrefs_cli = UgbCommandGroup(self.asm, "xref")
        xrefs_cli.add_group(declare_cli)
        xrefs_cli.add_command("auto", self.auto_declare)
        xrefs_cli.add_command("clear", self.clear)
        return xrefs_cli

    def save_items(self):
        for _type, _links in self._mappings.items():
            for _from, _to in _links.items():
                yield ('xref', 'declare', _type, _from, _to)
