from typing import TYPE_CHECKING, Dict, NamedTuple, Optional, Set

from .special_labels import SpecialLabel
from ..address import Address, ROM
from ..data_types import Byte, Word, Ref, IORef
from ..enums import Operation as Op

if TYPE_CHECKING:
    from .disassembler import Disassembler
    from .instructions import RawInstruction
    from .models import Value

__all__ = ['ContextManager']


class SavedContext(NamedTuple):
    address: Address
    force_scalar: bool
    bank: int


class ContextManager:
    def __init__(self, disassembler: "Disassembler"):
        self.asm = disassembler

        self.force_scalar: Set[Address] = set()
        self.bank_override: Dict[Address, int] = {}

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
            return 0

        if instr.type is Op.Load and instr.value_pos == 1:
            special = SpecialLabel.detect(target)
            if special is not None:
                return special

        return self.address_context(instr.address, target)

    def address_context(self, pos: Address, address: Address) -> "Value":
        if pos in self.force_scalar:
            return Word(address.memory_address)

        # Auto-detect ROM bank if current instruction requires one
        if address.bank < 0:
            if address.type is ROM and pos.bank > 0:
                bank = pos.bank
            else:
                bank = self.bank_override.get(pos, -1)
            if bank >= 0:
                address = Address(address.type, bank, address.offset)

        # Detect labels
        target_labels = self.asm.labels.get_labels(address) or [address]
        return target_labels[-1]

    def list_context(self):
        addresses = set(self.bank_override) | self.force_scalar
        for address in sorted(addresses):
            yield SavedContext(
                address,
                address in self.force_scalar,
                self.bank_override.get(address, -1),
            )