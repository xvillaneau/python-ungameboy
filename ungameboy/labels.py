from typing import Dict, List, NamedTuple, Optional

from .address import Address


class Label(NamedTuple):
    address: Address
    global_name: str
    local_name: str = ""

    @property
    def name(self):
        name = self.global_name
        if self.local_name:
            name += f".{self.local_name}"
        return name


class LabelManager:
    def __init__(self):
        self._by_address: Dict[Address, List[str]] = {}
        self._by_name: Dict[str, Address] = {}

    def labels_at(self, address: Address) -> List[Label]:
        names = self._by_address.get(address, [])
        return [Label(address, name) for name in names]

    def location_of(self, name: str) -> Optional[Address]:
        return self._by_name.get(name)

    def create(self, address: Address, name: str):
        if "." in name:
            raise NotImplementedError("Local labels are not supported yet")

        if name in self._by_name:
            existing_addr = self._by_name[name]
            if existing_addr == address:
                return
            else:
                raise ValueError(f"Label {name} already exists at {existing_addr}")

        self._by_name[name] = address
        self._by_address.setdefault(address, []).append(name)
