from dataclasses import dataclass
from typing import Dict


@dataclass
class DataBlock:
    address: int
    length: int
    description: str = ""

    def __contains__(self, item):
        if not isinstance(item, int):
            return False
        return self.address <= item < self.next_address

    @property
    def next_address(self):
        return self.address + self.length


@dataclass
class Empty(DataBlock):
    pass


class DataManager:
    def __init__(self):
        self.inventory: Dict[int, DataBlock] = {}

    def insert(self, data: DataBlock):
        if self.get_data(data.address) is not None:
            raise ValueError("Data overlap detected")
        if any(addr in data for addr in self.inventory):
            raise ValueError("Data overlap detected")
        self.inventory[data.address] = data

    def get_data(self, address):
        if address in self.inventory:
            return self.inventory[address]
        block_matches = (
            data for data in self.inventory.values()
            if address in data
        )
        return next(block_matches, None)
