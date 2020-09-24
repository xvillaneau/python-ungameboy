from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

import click

from .special_labels import SpecialLabel
from .labels import LabelOffset
from .manager_base import AsmManager
from ..address import Address, ROM
from ..commands import AddressOrLabel, ExtendedInt
from ..data_types import Byte, Word, Ref, IORef
from ..enums import Operation as Op

if TYPE_CHECKING:
    from .binary_data import RowItem
    from .disassembler import Disassembler
    from .instructions import RawInstruction
    from .models import Value

__all__ = ['ContextManager']


class ContextManager(AsmManager):
    def __init__(self, disassembler: "Disassembler"):
        super().__init__(disassembler)

        self.force_scalar: Set[Address] = set()
        self.bank_override: Dict[Address, int] = {}

    def reset(self) -> None:
        self.force_scalar.clear()
        self.bank_override.clear()

    def set_context(
            self,
            addr: Address,
            force_scalar: Optional[bool] = None,
            bank: Optional[int] = None,
    ):
        if force_scalar is not None:
            if force_scalar:
                self.force_scalar.add(addr)
            else:
                self.force_scalar.discard(addr)

        if bank is not None:
            if bank >= 0:
                self.bank_override[addr] = bank
            elif addr in self.bank_override:
                self.bank_override.pop(addr)

    def has_context(self, address: Address) -> bool:
        return address in self.force_scalar or address in self.bank_override

    def instruction_context(
            self, instr: "RawInstruction"
    ) -> Tuple["Value", Optional[Address]]:
        if instr.value_pos <= 0:
            return 0, None

        arg = instr.args[instr.value_pos - 1]
        if instr.address in self.force_scalar:
            return arg, None
        elif isinstance(arg, Word):
            target = Address.from_memory_address(arg)
        elif instr.type is Op.RelJump:
            target = instr.next_address + arg
        elif isinstance(arg, IORef) and isinstance(arg.target, Byte):
            target = Address.from_memory_address(arg.target + 0xff00)
        elif isinstance(arg, Ref) and isinstance(arg.target, Word):
            target = Address.from_memory_address(arg.target)
        else:
            return arg, None

        if instr.type is Op.Load and instr.value_pos == 1:
            special = SpecialLabel.detect(target)
            if special is not None:
                return special, None

        return (
            self.address_context(instr.address, target),
            self.detect_addr_bank(instr.address, target),
        )

    def row_context(
            self, row: List['RowItem'], address: Address
    ) -> Tuple[List['Value'], Optional[Address]]:
        n_addr, dest_addr, values = 0, None, []

        for item in row:
            if isinstance(item, Address):
                n_addr += 1
                dest_addr = dest_addr or item
                values.append(self.address_context(address, item))
            else:
                values.append(item)

        if n_addr == 1:
            dest_addr = self.detect_addr_bank(address, dest_addr)
        else:
            dest_addr = None

        return values, dest_addr

    def detect_addr_bank(self, pos: Address, ref: Address) -> Address:
        # Auto-detect ROM bank if current instruction requires one
        if ref.bank >= 0:
            return ref

        bank = self.bank_override.get(pos, -1)
        if bank < 0 < pos.bank and ref.type is ROM:
            bank = pos.bank

        return Address(ref.type, bank, ref.offset) if bank >= 0 else ref

    def address_context(
            self, pos: Address, address: Address, relative=False
    ) -> "Value":
        address = self.detect_addr_bank(pos, address)

        # Detect labels
        target_labels = self.asm.labels.get_labels(address)
        if relative:
            scope = target_labels or self.asm.labels.scope_at(address)
            if scope:
                label = scope[-1]
                offset = address.offset - label.address.offset
                return LabelOffset(label, offset)
        return target_labels[-1] if target_labels else address

    def build_cli(self) -> 'click.Command':
        context_cli = click.Group('context')
        address_arg = AddressOrLabel(self.asm)

        @context_cli.group('set')
        def set_context():
            pass

        @set_context.command("scalar")
        @click.argument('address', type=address_arg)
        def context_force_scalar(address: Address):
            self.set_context(address, force_scalar=True)
            return False

        @set_context.command("bank")
        @click.argument('address', type=address_arg)
        @click.argument("bank", type=ExtendedInt())
        def context_set_bank(address: Address, bank: int):
            self.set_context(address, bank=bank)
            return False

        @context_cli.command('clear')
        @click.argument('address', type=address_arg)
        def context_clear(address):
            self.set_context(address, force_scalar=False, bank=-1)
            return False

        return context_cli

    def save_items(self):
        addresses = set(self.bank_override) | self.force_scalar
        for address in sorted(addresses):
            if address in self.force_scalar:
                yield ('context', 'set', 'scalar', address)
            bank = self.bank_override.get(address, -1)
            if bank >= 0:
                yield ('context', 'set', 'bank', address, bank)
