from typing import TYPE_CHECKING, Dict, Optional, Set

import click

from .special_labels import SpecialLabel
from .labels import LabelOffset
from .manager_base import AsmManager
from ..address import Address, ROM
from ..commands import AddressOrLabel, ExtendedInt
from ..data_types import Byte, Word, Ref, IORef
from ..enums import Operation as Op

if TYPE_CHECKING:
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

    def instruction_context(self, instr: "RawInstruction") -> "Value":
        if instr.value_pos <= 0:
            return 0

        arg = instr.args[instr.value_pos - 1]
        if isinstance(arg, Word):
            target = Address.from_memory_address(arg)
        elif instr.type is Op.RelJump:
            target = instr.next_address + arg
        elif isinstance(arg, IORef) and isinstance(arg.target, Byte):
            target = Address.from_memory_address(arg.target + 0xff00)
        elif isinstance(arg, Ref) and isinstance(arg.target, Word):
            target = Address.from_memory_address(arg.target)
        else:
            return arg

        if instr.type is Op.Load and instr.value_pos == 1:
            special = SpecialLabel.detect(target)
            if special is not None:
                return special

        return self.address_context(instr.address, target)

    def address_context(
            self, pos: Address,
            address: Address,
            ignore_scalar=False,
            allow_relative=False,
    ) -> "Value":
        if pos in self.force_scalar and not ignore_scalar:
            return Word(address.memory_address)

        # Auto-detect ROM bank if current instruction requires one
        if address.bank < 0:
            bank = self.bank_override.get(pos, -1)
            if bank < 0 < pos.bank and address.type is ROM:
                bank = pos.bank
            if bank >= 0:
                address = Address(address.type, bank, address.offset)

        # Detect labels
        target_labels = self.asm.labels.get_labels(address)
        if allow_relative and not target_labels:
            scope = self.asm.labels.scope_at(address)
            if scope:
                label = scope[-1]
                offset = address.offset - label.address.offset
                return LabelOffset(label, offset)
        return target_labels[-1] if target_labels else address

    def build_cli(self) -> 'click.Command':
        context_cli = click.Group('context')
        address_arg = AddressOrLabel(self.asm)

        @context_cli.command("force-scalar")
        @click.argument('address', type=address_arg)
        def context_force_scalar(address: Address):
            self.set_context(address, force_scalar=True)
            return False

        @context_cli.command("no-force-scalar")
        @click.argument('address', type=address_arg)
        def context_no_force_scalar(address: Address):
            self.set_context(address, force_scalar=False)
            return False

        @context_cli.command("force-bank")
        @click.argument('address', type=address_arg)
        @click.argument("bank", type=ExtendedInt())
        def context_set_bank(address: Address, bank: int):
            self.set_context(address, bank=bank)
            return False

        @context_cli.command("no-force-bank")
        @click.argument('address', type=address_arg)
        def context_no_bank(address: Address):
            self.set_context(address, bank=-1)
            return False

        return context_cli

    def save_items(self):
        addresses = set(self.bank_override) | self.force_scalar
        for address in sorted(addresses):
            if address in self.force_scalar:
                yield ('context', 'force-scalar', address)
            bank = self.bank_override.get(address, -1)
            if bank >= 0:
                yield ('context', 'force-bank', address, bank)
