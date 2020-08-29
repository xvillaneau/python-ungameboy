from typing import NamedTuple, Optional

from .address import Address
from .data_structures import AddressMapping


class Section(NamedTuple):
    address: Address
    name: str


class SectionManager:
    def __init__(self):
        self._sections: AddressMapping[str] = AddressMapping()

    def create(self, address: Address, name: str):
        if '"' in name:
            raise ValueError("Section name cannot contain double quote")
        existing = self._sections.get(address)
        if existing is None:
            pass
        elif existing == name:
            return
        else:
            raise ValueError(f"There is already a section at {address}")
        if name in self._sections.values():
            raise ValueError(f"There is already a section named {name!r}")

        self._sections[address] = name

    def get_section(self, address: Address) -> Optional[Section]:
        name = self._sections.get(address)
        if name is None:
            return None
        else:
            return Section(address, name)

    def list_sections(self):
        for addr, name in self._sections.items():
            yield Section(addr, name)
