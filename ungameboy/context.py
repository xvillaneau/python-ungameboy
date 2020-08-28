from typing import Dict, NamedTuple, Optional, Set

from .address import Address


class SavedContext(NamedTuple):
    address: Address
    force_scalar: bool
    bank: int


class ContextManager:
    def __init__(self):
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

    def get_context(self, address: Address):
        return SavedContext(
            address,
            address in self.force_scalar,
            self.bank_override.get(address, -1),
        )

    def list_context(self):
        addresses = set(self.bank_override) | self.force_scalar
        for addr in sorted(addresses):
            yield self.get_context(addr)
