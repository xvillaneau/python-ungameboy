from typing import TYPE_CHECKING, Dict, Optional, List, Tuple, Type, Union

import click

from .manager_base import AsmManager
from ..commands import AddressOrLabel
from ..address import Address
from ..data_structures import AddressMapping
from ..data_types import Byte, ParameterMeta, Word

if TYPE_CHECKING:
    from .decoder import ROMBytes
    from .disassembler import Disassembler

__all__ = ['ROW_TYPES_NAMES', 'DataBlock', 'DataTable', 'DataManager']

RowItem = Union[Byte, Word, Address]
RowType = Type[RowItem]

ROW_TYPES_NAMES: List[Tuple[str, RowType]] = [
    ('db', Byte), ('dw', Word), ('addr', Address)
]
DATA_TYPES = {name: obj for name, obj in ROW_TYPES_NAMES}
TYPES_NAMES = {obj: name for name, obj in ROW_TYPES_NAMES}


class DataBlock:
    row_size: int = 8
    description: str = ''

    def __init__(self, address: Address, size: int):
        self.address = address
        self.bytes = b''
        self.size = size

    def __getitem__(self, item) -> List[RowItem]:
        if not isinstance(item, int):
            raise TypeError()
        data = self.get_row_bin(item)
        return [Byte(b) for b in data]

    def __iter__(self):
        for row in range(self.rows):
            yield self[row]

    def load_from_rom(self, rom: 'ROMBytes'):
        pos = self.address.rom_file_offset
        self.bytes = rom[pos:pos + self.size]

    @property
    def rows(self) -> int:
        return (self.size + self.row_size - 1) // self.row_size

    def get_row_bin(self, row: int) -> bytes:
        if not 0 <= row < self.rows:
            raise IndexError("Row index out of range")
        size = self.row_size
        return self.bytes[size * row:size * (row + 1)]

    @property
    def create_cmd(self):
        return ('data', 'create-simple', self.address, self.size)


class DataTable(DataBlock):
    def __init__(self, address: Address, rows: int, row_struct: List[RowType]):
        self.row_struct = row_struct
        self.row_size = sum(
            item.n_bytes if isinstance(item, ParameterMeta) else 2
            for item in self.row_struct
        )
        self._rows = rows
        super().__init__(address, rows * self.row_size)

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

    @property
    def description(self) -> str:
        return f"{self.rows} rows"

    @property
    def rows(self):
        return self._rows

    @property
    def create_cmd(self):
        row = ','.join(TYPES_NAMES[obj] for obj in self.row_struct)
        return ('data', 'create-table', self.address, self.rows, row)


class RLEDataBlock(DataBlock):
    def __init__(self, address: Address):
        super().__init__(address, 0)
        self.unpacked_data = b''

    def load_from_rom(self, rom: 'ROMBytes'):
        data = []
        start_pos = pos = self.address.rom_file_offset
        byte = rom[pos]
        while byte != 0:
            pos += 1
            pkg_type, arg = divmod(byte, 0x80)

            if pkg_type > 0:  # Data
                data.extend(rom[pos:pos + arg])
                pos += arg
            else:  # RLE
                value = rom[pos]
                data.extend(value for _ in range(arg))
                pos += 1

            byte = rom[pos]

        self.bytes = rom[start_pos:pos + 1]
        self.unpacked_data = bytes(data)
        self.size = pos - start_pos + 1

    @property
    def description(self) -> str:
        return f'{len(self.unpacked_data)} bytes decompressed'

    @property
    def create_cmd(self):
        return ('data', 'create-rle', self.address)


class DataManager(AsmManager):

    def __init__(self, disassembler: 'Disassembler'):
        super().__init__(disassembler)

        self.inventory: Dict[Address, DataBlock] = {}
        self._blocks_map: AddressMapping[int] = AddressMapping()

    def reset(self):
        self.inventory.clear()
        self._blocks_map.clear()

    def create(self, address: Address, size: int):
        self._insert(DataBlock(address, size))

    def create_table(self, address: Address, rows: int, structure: List[RowType]):
        self._insert(DataTable(address, rows, structure))

    def create_rle(self, address: Address):
        self._insert(RLEDataBlock(address))

    def _insert(self, data: DataBlock):
        data.load_from_rom(self.asm.rom)
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

    def build_cli(self) -> click.Command:

        data_cli = click.Group('data')
        address_arg = AddressOrLabel(self.asm)

        @data_cli.command('create-simple')
        @click.argument('address', type=address_arg)
        @click.argument('size', type=int)
        def data_create_simple(address: Address, size):
            self.create(address, size)

        @data_cli.command('create-table')
        @click.argument('address', type=address_arg)
        @click.argument('rows', type=int)
        @click.argument('structure', type=str)
        def data_create_table(address: Address, rows: int, structure: str):
            struct = [DATA_TYPES[item] for item in structure.split(',')]
            self.create_table(address, rows, struct)

        @data_cli.command('create-rle')
        @click.argument('address', type=address_arg)
        def data_create_rle(address: Address):
            self.create_rle(address)

        return data_cli

    def save_items(self):
        for addr in sorted(self.inventory):
            yield self.inventory[addr].create_cmd
