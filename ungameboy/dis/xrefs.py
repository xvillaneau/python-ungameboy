from typing import TYPE_CHECKING, NamedTuple, Set, Tuple

from .data import DataTable, Jumptable
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
    refers_to: Set[Address]
    referred_by: Set[Address]


class LinksCollection:
    def __init__(self):
        self.refs_out: AddressMapping[Set[Address]] = AddressMapping()
        self.refs_in: AddressMapping[Set[Address]] = AddressMapping()

    def reset(self):
        self.refs_out.clear()
        self.refs_in.clear()

    def items(self):
        return self.refs_out.items()

    def has_link(self, addr_from: Address, addr_to: Address):
        return addr_to in self.refs_out.get(addr_from, ())

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

    def clear_incoming(self, address: Address):
        refs_in = list(self.refs_in.get(address, ()))
        for addr_from in refs_in:
            self.remove_link(addr_from, address)

    def clear_outgoing(self, address: Address):
        refs_out = list(self.refs_out.get(address, ()))
        for addr_to in refs_out:
            self.remove_link(address, addr_to)

    def clear(self, address: Address):
        self.clear_outgoing(address)

    def incoming(self, address: Address) -> Set[Address]:
        return self.refs_in.get(address, set())

    def outgoing(self, address: Address) -> Set[Address]:
        return self.refs_out.get(address, set())

    def get_links(self, address: Address) -> Tuple[Set[Address], Set[Address]]:
        return self.outgoing(address), self.incoming(address)


class XRefCollection:
    def __init__(self):
        super().__init__()
        self.auto = LinksCollection()
        self.manual = LinksCollection()

    def reset(self):
        self.manual.reset()
        self.auto.reset()

    def create_link(self, addr_from: Address, addr_to: Address, auto=False):
        if self.auto.has_link(addr_from, addr_to):
            return
        if auto and self.manual.has_link(addr_from, addr_to):
            self.manual.remove_link(addr_from, addr_to)
        links = self.auto if auto else self.manual
        links.create_link(addr_from, addr_to)

    def clear(self, address: Address):
        self.auto.clear(address)
        self.manual.clear(address)

    def incoming(self, address: Address) -> Set[Address]:
        return self.manual.incoming(address) | self.auto.incoming(address)

    def outgoing(self, address: Address) -> Set[Address]:
        return self.manual.outgoing(address) | self.auto.outgoing(address)

    def get_links(
            self, address: Address, include_auto=True
    ) -> Tuple[Set[Address], Set[Address]]:
        links = self if include_auto else self.manual
        return links.outgoing(address), links.incoming(address)


class XRefManager(AsmManager):
    TERMINATING = {Op.AbsJump, Op.RelJump, Op.Return, Op.ReturnIntEnable}

    def __init__(self, asm: "Disassembler"):
        super().__init__(asm)
        self.bypass_index = False

        self._mappings = {
            'call': XRefCollection(),
            'jump': XRefCollection(),
            'read': XRefCollection(),
            'write': XRefCollection(),
            'ref': XRefCollection(),
        }

    def reset(self) -> None:
        for collection in self._mappings.values():
            collection.reset()

    def index_data(self, address: Address, fast=False, single=False):
        data = self.asm.data.get_data(address)
        if data is None:
            return False

        if not isinstance(data, DataTable):
            return True
        ref = "jump" if isinstance(data, Jumptable) else "ref"

        offset = address.offset - data.address.offset
        row_n = offset // data.row_size
        address = data.address + row_n * data.row_size
        if not 0 <= row_n < data.rows:
            return True

        get_bank = self.asm.context.detect_addr_bank
        while row_n < data.rows:
            if not fast:
                self.clear(address)

            address = data.address + row_n * data.row_size
            targets = [
                get_bank(address, obj)
                for obj in data.get_row(row_n)
                if isinstance(obj, Address)
            ]
            if not targets:
                return True

            for target in targets:
                self._mappings[ref].create_link(address, target, auto=True)

            if single:
                return True

            row_n += 1

        return True

    def index_from(
            self, address: Address, fast=False, single=False
    ) -> Address:
        if self.asm.rom is None or self.bypass_index:
            return address

        get_instr = self.asm.rom.decode_instruction
        get_value = self.asm.context.instruction_value
        terminating = {Op.AbsJump, Op.RelJump, Op.Return, Op.ReturnIntEnable}

        bank = address.bank
        while address.bank == bank and address.is_valid:
            if self.index_data(address, fast, single):
                break

            if not fast:
                self.clear(address, _index=False)

            instr = get_instr(address.rom_file_offset)
            address = instr.next_address
            op = instr.type
            if op in (Op.Invalid, Op.ReturnIntEnable):
                break

            target = get_value(instr)
            if isinstance(target, Address) and target.bank >= 0:
                ref_type = ''
                if op in (Op.Load, Op.LoadFast):
                    arg = instr.args[instr.value_pos - 1]
                    if isinstance(arg, Ref):
                        ref_type = ('', 'write', 'read')[instr.value_pos]
                    else:
                        ref_type = 'ref'
                elif op in (Op.Call, Op.Vector):
                    ref_type = 'call'
                elif op is Op.AbsJump:  # Ignore relative jumps
                    ref_type = 'jump'

                if ref_type:
                    self._mappings[ref_type].create_link(
                        instr.address, target, auto=True
                    )

            if single:
                break

            arg0 = instr.args[0] if instr.args else None
            if op in terminating and not isinstance(arg0, Condition):
                break

        return address

    def index(self, bank: int, fast=False):
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
            prev_addr = self.index_from(addr, fast=fast)

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

    def clear(self, address: Address, _index=True):
        for links in self._mappings.values():
            links.clear(address)
        if _index:
            self.index_from(address, single=True)

    def clear_range(self, addr_start: Address, length: int):
        for offset in range(length):
            self.clear(addr_start + offset)

    def count_incoming(self, link_type: str, address: Address):
        return len(self._mappings[link_type].incoming(address))

    def get_xrefs(self, address: Address, include_auto=True) -> XRefs:
        return XRefs(
            address,
            *(
                arg
                for links in self._mappings.values()
                for arg in links.get_links(address, include_auto)
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
            for _from, _tos in _links.manual.items():
                for _to in _tos:
                    yield ('xref', 'declare', _type, _from, _to)
