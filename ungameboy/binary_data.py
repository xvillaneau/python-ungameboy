from typing import TYPE_CHECKING, Dict, Optional, List, Tuple, Type, Union

from .address import Address
from .data_structures import SortedMapping
from .data_types import Byte, ParameterMeta, Word

if TYPE_CHECKING:
    from .disassembler import Disassembler

RowItem = Union[Byte, Word, Address]
RowItemType = Type[RowItem]

ROW_TYPES_NAMES: List[Tuple[str, RowItemType]] = [
    ('db', Byte), ('dw', Word), ('addr', Address)
]


class DataBlock:
    def __init__(self, address: Address, data: bytes, row_size=8):
        self.address = address
        self.bytes = data
        self.row_size = row_size

    def __getitem__(self, item) -> List[RowItem]:
        if not isinstance(item, int):
            raise TypeError()
        data = self.get_row_bin(item)
        return [Byte(b) for b in data]

    def __iter__(self):
        for row in range(self.rows):
            yield self[row]

    def get_row_bin(self, row: int) -> bytes:
        if not 0 <= row < self.rows:
            raise IndexError("Row index out of range")
        size = self.row_size
        return self.bytes[size * row:size * (row + 1)]

    @property
    def size(self):
        return len(self.bytes)

    @property
    def rows(self) -> int:
        return (self.size + self.row_size - 1) // self.row_size


class DataTable(DataBlock):
    def __init__(self, address: Address, data: bytes, row_struct: List[RowItemType]):
        self.row_struct = row_struct
        super().__init__(address, data, self.get_row_size(row_struct))

    def __getitem__(self, item) -> List[RowItem]:
        row, row_bytes = [], self.get_row_bin(item)

        for t in self.row_struct:
            n_bytes = 2 if t is Address else t.n_bytes
            value = int.from_bytes(row_bytes[:n_bytes], 'little')
            row_bytes = row_bytes[n_bytes:]
            if t is Address:
                row.append(Address.from_memory_address(value))
            else:
                row.append(t(value))

        return row

    @classmethod
    def get_row_size(cls, row_struct: List[RowItemType]) -> int:
        return sum(
            item.n_bytes if isinstance(item, ParameterMeta) else 2
            for item in row_struct
        )


class DataManager:
    def __init__(self, asm: "Disassembler"):
        self.asm = asm

        self.inventory: Dict[Address, DataBlock] = {}
        self._blocks_map: SortedMapping[Address, int] = SortedMapping()

    def create(self, address: Address, length=1):
        content = self._get_bytes(address, length)
        self._insert(DataBlock(address, content))

    def create_table(
            self, address: Address, rows: int, structure: List[RowItemType]
    ):
        row_size = DataTable.get_row_size(structure)
        data = self._get_bytes(address, row_size * rows)
        block = DataTable(address, data, structure)
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
