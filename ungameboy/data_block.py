from dataclasses import dataclass
from typing import Dict, Optional

from .address import Address
from .data_structures import SortedMapping


@dataclass
class DataBlock:
    address: Address
    length: int
    description: str = ""

    def __contains__(self, item):
        if not isinstance(item, Address):
            return False
        return self.address <= item < self.next_address

    @property
    def next_address(self) -> Address:
        return self.address + self.length


@dataclass
class Empty(DataBlock):
    pass


class DataManager:
    def __init__(self):
        self.inventory: Dict[Address, DataBlock] = {}
        self._blocks_map: SortedMapping[Address, int] = SortedMapping()

    def create(self, address: Address, length=1, description=''):
        block = DataBlock(address, length, description)
        self.insert(block)

    def insert(self, data: DataBlock):
        next_blk = self.next_block(data.address)
        if next_blk is not None and next_blk.address < data.next_address:
            raise ValueError("Data overlap detected")

        self.inventory[data.address] = data
        self._blocks_map[data.address] = data.length

    def next_block(self, address) -> Optional[DataBlock]:
        try:
            addr, _ = self._blocks_map.get_ge(address)
        except LookupError:
            return None
        return self.inventory[addr]

    def get_data(self, address):
        try:
            addr, size = self._blocks_map.get_le(address)
        except LookupError:
            return None
        if address >= addr + size:
            return None
        return self.inventory[addr]

    def list_items(self):
        for addr in sorted(self.inventory):
            yield self.inventory[addr]
