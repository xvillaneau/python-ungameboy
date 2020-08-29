from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional, List, Tuple, Type, Union

from .address import Address
from .data_structures import SortedMapping
from .data_types import Byte, ParameterMeta, Word

if TYPE_CHECKING:
    from .disassembler import Disassembler

TableCol = Union[ParameterMeta, Type[Address]]

ROW_TYPES_NAMES: List[Tuple[str, TableCol]] = [
    ('db', Byte), ('dw', Word), ('addr', Address)
]


@dataclass
class DataBlock:
    address: Address
    size: int
    bytes: bytes

    @property
    def data_lines(self):
        return 0


@dataclass
class DataTable(DataBlock):
    rows: int
    row_struct: List[TableCol]

    def __post_init__(self):
        self.size = self.rows * self.row_size

    def __iter__(self):
        for row in range(self.rows):
            yield self[row]

    def __getitem__(self, item):
        if not isinstance(item, int):
            raise TypeError()
        if not 0 <= item < self.rows:
            raise IndexError("Row index out of range")

        start = item * self.row_size
        stop = start + self.row_size
        row_bytes = self.bytes[start:stop]

        row = []
        for t in self.row_struct:
            n_bytes = 2 if t is Address else t.n_bytes
            value = int.from_bytes(row_bytes[:n_bytes], 'little')
            row_bytes = row_bytes[n_bytes:]
            if t is Address:
                row.append(Address.from_memory_address(value))
            else:
                row.append(t(value))

        return row

    @property
    def data_lines(self):
        return self.rows

    @property
    def row_size(self):
        return sum(
            item.n_bytes if isinstance(item, ParameterMeta) else 2
            for item in self.row_struct
        )


class DataManager:
    def __init__(self, asm: "Disassembler"):
        self.asm = asm

        self.inventory: Dict[Address, DataBlock] = {}
        self._blocks_map: SortedMapping[Address, int] = SortedMapping()

    def create(self, address: Address, length=1):
        content = self._get_bytes(address, length)
        self._insert(DataBlock(address, length, content))

    def create_table(
            self, address: Address, rows: int, structure: List[TableCol]
    ):
        block = DataTable(address, 0, b'', rows, structure)
        block.bytes = self._get_bytes(address, block.size)
        self._insert(block)

    def _get_bytes(self, start: Address, size: int):
        stop = start + size
        return self.asm.rom[start.rom_file_offset:stop.rom_file_offset]

    def _insert(self, data: DataBlock):
        next_blk = self.next_block(data.address)
        end_addr = data.address + data.size
        if next_blk is not None and next_blk.address < end_addr:
            raise ValueError("Data overlap detected")

        self.inventory[data.address] = data
        self._blocks_map[data.address] = data.size

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
