from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Union

import click

from .manager_base import AsmManager
from ..commands import AddressOrLabel, ExtendedInt
from ..address import Address
from ..data_structures import AddressMapping
from ..data_types import Byte, CgbColor, Word

if TYPE_CHECKING:
    from .decoder import ROMBytes
    from .disassembler import Disassembler

__all__ = ['ROW_TYPES', 'DataBlock', 'DataTable', 'DataManager', 'RowItem']

RowItem = Union[Byte, CgbColor, Word, Address]


@dataclass(frozen=True)
class RowType:
    name: str
    type: Callable[[int], RowItem]
    n_bytes: int = 2
    endian: str = 'little'


ROW_TYPES: List[RowType] = [
    RowType('db', Byte, n_bytes=1),
    RowType('dw', Word),
    RowType('addr', Address.from_memory_address),
    RowType('addr_be', Address.from_memory_address, endian='big'),
    RowType('color', CgbColor),
    RowType('color_be', CgbColor, endian='big'),
]
TYPES_BY_NAME = {obj.name: obj for obj in ROW_TYPES}


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

    @property
    def end_address(self) -> Address:
        return self.address + self.size

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
        self.row_size = sum(item.n_bytes for item in self.row_struct)
        self._rows = rows
        super().__init__(address, rows * self.row_size)

    def __getitem__(self, item) -> List[RowItem]:
        row_bytes = self.get_row_bin(item)
        row_values, pos = [], 0

        for t in self.row_struct:
            value = int.from_bytes(row_bytes[pos:pos + t.n_bytes], t.endian)
            row_values.append(t.type(value))
            pos += t.n_bytes

        return row_values

    @property
    def description(self) -> str:
        return f"{self.rows} × " + ','.join(t.name for t in self.row_struct)

    @property
    def rows(self):
        return self._rows

    @property
    def create_cmd(self):
        row = ','.join(obj.name for obj in self.row_struct)
        return ('data', 'create-table', self.address, self.rows, row)


class PaletteData(DataTable):
    def __init__(self, address: Address, rows: int = 8):
        color_type = TYPES_BY_NAME['color']
        super().__init__(address, rows, [color_type] * 4)

    @property
    def create_cmd(self):
        return ('data', 'create-palette', self.address, self.rows)


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

    def create_palette(self, address: Address, rows: int):
        self._insert(PaletteData(address, rows))

    def create_rle(self, address: Address):
        self._insert(RLEDataBlock(address))

    def delete(self, address: Address):
        if address not in self.inventory:
            raise IndexError(address)
        del self.inventory[address]
        del self._blocks_map[address]

    def _insert(self, data: DataBlock):
        data.load_from_rom(self.asm.rom)

        prev_blk = self.get_data(data.address)
        if prev_blk and prev_blk.end_address > data.address:
            raise ValueError("Data overlap detected")

        next_blk = self.next_block(data.address)
        if next_blk and next_blk.address < data.end_address:
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
        @click.argument('size', type=ExtendedInt())
        def data_create_simple(address: Address, size):
            self.create(address, size)

        @data_cli.command('create-table')
        @click.argument('address', type=address_arg)
        @click.argument('rows', type=ExtendedInt())
        @click.argument('structure', type=str)
        def data_create_table(address: Address, rows: int, structure: str):
            struct = [TYPES_BY_NAME[item] for item in structure.split(',')]
            self.create_table(address, rows, struct)

        @data_cli.command('create-palette')
        @click.argument('address', type=address_arg)
        @click.argument('rows', type=int, default=8)
        def data_create_palette(address, rows):
            self.create_palette(address, rows)

        @data_cli.command('create-rle')
        @click.argument('address', type=address_arg)
        def data_create_rle(address: Address):
            self.create_rle(address)

        @data_cli.command('delete')
        @click.argument('address', type=address_arg)
        def data_delete(address: Address):
            self.delete(address)

        return data_cli

    def save_items(self):
        for addr in sorted(self.inventory):
            yield self.inventory[addr].create_cmd
