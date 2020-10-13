from typing import TYPE_CHECKING, NamedTuple, Set, Tuple

from .manager_base import AsmManager
from .models import DataRow, Instruction
from ..address import ROM, Address
from ..commands import UgbCommandGroup
from ..data_structures import AddressMapping
from ..data_types import Ref
from ..enums import Condition, Operation as Op

if TYPE_CHECKING:
    from .disassembler import Disassembler


class XRefs(NamedTuple):
    address: Address
    calls: Set[Address]
    called_by: Set[Address]
    jumps_to: Set[Address]
    jumps_from: Set[Address]
    reads: Set[Address]
    read_by: Set[Address]
    writes_to: Set[Address]
    written_by: Set[Address]


class LinksCollection:
    def __init__(self):
        self.refs_out: AddressMapping[Set[Address]] = AddressMapping()
        self.refs_in: AddressMapping[Set[Address]] = AddressMapping()

    def reset(self):
        self.refs_out.clear()
        self.refs_in.clear()

    def items(self):
        return self.refs_out.items()

    def create_link(self, addr_from: Address, addr_to: Address):
        self.refs_out.setdefault(addr_from, set()).add(addr_to)
        self.refs_in.setdefault(addr_to, set()).add(addr_from)

    def remove_link(self, addr_from: Address, addr_to: Address):
        if addr_from in self.refs_in.get(addr_to, ()):
            self.refs_in[addr_to].remove(addr_from)
            if not self.refs_in[addr_to]:
                del self.refs_in[addr_to]
        if addr_to in self.refs_out.get(addr_from, ()):
            self.refs_out[addr_from].remove(addr_to)
            if not self.refs_out[addr_from]:
                del self.refs_out[addr_from]

    def clear(self, address: Address):
        refs_out = list(self.refs_out.get(address, ()))
        for addr_to in refs_out:
            self.remove_link(address, addr_to)
        refs_in = list(self.refs_in.get(address, ()))
        for addr_from in refs_in:
            self.remove_link(addr_from, address)

    def get_links(self, address: Address) -> Tuple[Set[Address], Set[Address]]:
        _in, _out = self.refs_in.get(address), self.refs_out.get(address)
        return _out or set(), _in or set()


class XRefManager(AsmManager):
    def __init__(self, asm: "Disassembler"):
        super().__init__(asm)

        self._mappings = {
            'call': LinksCollection(),
            'jump': LinksCollection(),
            'read': LinksCollection(),
            'write': LinksCollection(),
        }

    def reset(self) -> None:
        for collection in self._mappings.values():
            collection.reset()

    def index_all(self):
        pass

    def index_from(self, address: Address) -> Address:
        if self.asm.rom is None:
            return address

        get_data = self.asm.data.get_data
        get_instr = self.asm.rom.decode_instruction
        get_value = self.asm.context.instruction_value
        terminating = {Op.AbsJump, Op.RelJump, Op.Return, Op.ReturnIntEnable}

        bank = address.bank
        while address.bank == bank and address.is_valid:
            data = get_data(address)
            if data is not None:
                break

            instr = get_instr(address.rom_file_offset)
            if instr.type is Op.Invalid:
                break

            target = get_value(instr)
            if not isinstance(target, Address):
                address = instr.next_address
                continue

            op = instr.type
            ref_type = ''
            if op in (Op.Call, Op.Vector):
                ref_type = 'call'
            elif op is Op.AbsJump:  # Ignore relative jumps
                ref_type = 'jump'
            elif op in (Op.Load, Op.LoadFast):
                arg = instr.args[instr.value_pos - 1]
                if isinstance(arg, Ref):
                    ref_type = ('', 'write', 'read')[instr.value_pos]

            if ref_type:
                self._mappings[ref_type].create_link(instr.address, target)
            address = instr.next_address

            arg0 = instr.args[0] if instr.args else None
            if op in terminating and not isinstance(arg0, Condition):
                break

        return address

    def index(self, bank: int):
        if self.asm.rom is None:
            return

        pos = [addr for addr, _ in self.asm.labels.get_all_in_bank(ROM, bank)]
        if not pos:
            return

        pos.reverse()
        prev_addr = pos[-1]

        while pos:
            addr = pos.pop()
            if prev_addr > addr:
                continue
            prev_addr = self.index_from(addr)

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
        links = self._mappings[link_type].refs_in
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
        xrefs_cli.add_command("index", self.index)
        return xrefs_cli

    def save_items(self):
        for _type, _links in self._mappings.items():
            for _from, _tos in _links.items():
                for _to in _tos:
                    yield ('xref', 'declare', _type, _from, _to)
