from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple

from .special_labels import SpecialLabel
from .labels import LabelOffset
from .manager_base import AsmManager
from ..address import Address, ROM
from ..commands import UgbCommandGroup
from ..data_types import Byte, Word, Ref, IORef
from ..enums import Operation as Op

if TYPE_CHECKING:
    from .data import Row
    from .disassembler import Disassembler
    from .instructions import RawInstruction
    from .models import Value

__all__ = ['ContextManager']


class ContextManager(AsmManager):
    def __init__(self, asm: "Disassembler"):
        super().__init__(asm)

        self.force_scalar: Set[Address] = set()
        self.bank_override: Dict[Address, int] = {}

    def reset(self) -> None:
        self.force_scalar.clear()
        self.bank_override.clear()

    def set_force_scalar(self, address: Address):
        self.force_scalar.add(address)
        self.asm.xrefs.index_from(address, single=True)

    def set_bank_number(self, address: Address, bank: int):
        if bank >= 0:
            self.bank_override[address] = bank
        elif address in self.bank_override:
            self.bank_override.pop(address)
        self.asm.xrefs.index_from(address, single=True)

    def clear_context(self, address: Address):
        self.force_scalar.discard(address)
        if address in self.bank_override:
            self.bank_override.pop(address)
        self.asm.xrefs.index_from(address, single=True)

    def has_context(self, address: Address) -> bool:
        return address in self.force_scalar or address in self.bank_override

    def instruction_value(self, instr: "RawInstruction") -> "Value":
        if instr.value_pos <= 0:
            return 0

        arg = instr.args[instr.value_pos - 1]
        if instr.address in self.force_scalar:
            return arg
        elif isinstance(arg, Word):
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

        return self.detect_addr_bank(instr.address, target)

    def instruction_context(
            self, instr: "RawInstruction"
    ) -> Tuple["Value", Optional[Address]]:
        value = self.instruction_value(instr)
        if isinstance(value, Address):
            return self.address_context(instr.address, value), value
        else:
            return value, None

    def row_context(self, row: 'Row') -> Tuple[List['Value'], Optional[Address]]:
        n_addr, dest_addr, values = 0, None, []

        for item in row.items:
            if isinstance(item, Address):
                n_addr += 1
                dest_addr = dest_addr or item
                values.append(self.address_context(row.address, item))
            else:
                values.append(item)

        if n_addr == 1:
            dest_addr = self.detect_addr_bank(row.address, dest_addr)
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

    def build_cli_v2(self) -> 'UgbCommandGroup':
        context_set = UgbCommandGroup(self.asm, "set")
        context_set.add_command("scalar", self.set_force_scalar)
        context_set.add_command("bank", self.set_bank_number)

        context_cli = UgbCommandGroup(self.asm, "context")
        context_cli.add_group(context_set)
        context_cli.add_command("clear", self.clear_context)
        return context_cli

    def save_items(self):
        addresses = set(self.bank_override) | self.force_scalar
        for address in sorted(addresses):
            if address in self.force_scalar:
                yield ('context', 'set', 'scalar', address)
            bank = self.bank_override.get(address, -1)
            if bank >= 0:
                yield ('context', 'set', 'bank', address, bank)
