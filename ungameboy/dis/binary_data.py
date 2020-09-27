from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Union

import click

from .decoder import HeaderDecoder
from .manager_base import AsmManager
from ..commands import AddressOrLabel, ExtendedInt, UgbCommandGroup
from ..address import Address
from ..data_structures import AddressMapping
from ..data_types import Byte, CgbColor, Word

if TYPE_CHECKING:
    from .decoder import ROMBytes
    from .disassembler import Disassembler

__all__ = [
    'BaseData', 'BinaryData', 'CartridgeHeader', 'DataTable',
    'DataManager', 'EmptyData', 'RLEDataBlock', 'RowItem',
]

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


class BaseData(metaclass=ABCMeta):
    description: str = ''

    def __init__(self, address: Address, size: int):
        self.address = address
        self.bytes = b''
        self.size = size

    @property
    def end_address(self) -> Address:
        return self.address + self.size

    def load_from_rom(self, rom: 'ROMBytes'):
        pos = self.address.rom_file_offset
        self.bytes = rom[pos:pos + self.size]

    @property
    @abstractmethod
    def create_cmd(self):
        pass


class BinaryData(BaseData):
    row_size: int = 8

    def __getitem__(self, item) -> List[RowItem]:
        if not isinstance(item, int):
            raise TypeError()
        data = self.get_row_bin(item)
        return [Byte(b) for b in data]

    def __iter__(self):
        for row in range(self.rows):
            yield self[row]

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
        return ('data', 'create', 'simple', self.address, self.size)


class DataTable(BinaryData):
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
        return ('data', 'create', 'table', self.address, self.rows, row)


class JumpTable(DataTable):
    def __init__(self, address: Address, rows: int = 0):
        super().__init__(address, rows, [TYPES_BY_NAME['addr']])

    def load_from_rom(self, rom: 'ROMBytes'):
        if self.rows <= 0:
            # Auto-detect the table length, assuming it contains the
            # address right after the end of the table.
            self._rows = 0
            start = self.address.memory_address
            min_pos = 0xffff

            while (start + self.rows * 2) < min_pos:
                pos = (self.address + self.rows * 2).rom_file_offset
                self._rows += 1
                row_bin = rom[pos:pos + 2]
                row_pos = int.from_bytes(row_bin, 'little')
                if start < row_pos < min_pos:
                    min_pos = row_pos

            if not self.rows:
                raise ValueError("Failed to detect jump table")

            self.size = self.rows * 2

        super().load_from_rom(rom)

    @property
    def description(self) -> str:
        return f"Jump table, {self.rows} addresses"

    @property
    def create_cmd(self):
        return ("data", "create", "jumptable", self.address, self.rows)


class PaletteData(DataTable):
    def __init__(self, address: Address, rows: int = 8):
        color_type = TYPES_BY_NAME['color']
        super().__init__(address, rows, [color_type] * 4)

    @property
    def create_cmd(self):
        return ('data', 'create', 'palette', self.address, self.rows)


class RLEDataBlock(BinaryData):
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
        return ('data', 'create', 'rle', self.address)


class InterlacedRLEDataBlock(RLEDataBlock):
    def __init__(self, address: Address, full_size: int):
        super().__init__(address)
        self.full_size = full_size

    def load_from_rom(self, rom: 'ROMBytes'):
        data = []
        start_pos = pos = self.address.rom_file_offset
        byte = rom[pos]
        while byte != 0:
            pos += 1
            pkg_type, arg = divmod(byte, 0x80)
            remaining = self.full_size - len(data)

            if pkg_type > 0:  # Data
                packet = rom[pos:pos + arg]
                pos += min(arg, remaining)
            else:  # RLE
                packet = [rom[pos]] * arg
                pos += 1
            data.extend(packet[:remaining])

            if len(data) == self.full_size:
                break
            byte = rom[pos]
        else:
            pos += 1

        half = self.full_size // 2
        data = [
            data[i // 2 + half * (i % 2)]
            for i in range(self.full_size)
        ]

        self.bytes = rom[start_pos:pos]
        self.unpacked_data = bytes(data)
        self.size = pos - start_pos

    @property
    def create_cmd(self):
        return (
            'data', 'create', 'interlaced_rle', self.address, self.full_size
        )


class SGBPacket(BinaryData):
    COMMANDS = [
        ('PAL01', 'Set SGB Palette 0,1 Data'),
        ('PAL23', 'Set SGB Palette 2,3 Data'),
        ('PAL03', 'Set SGB Palette 0,3 Data'),
        ('PAL12', 'Set SGB Palette 1,2 Data'),
        ('ATTR_BLK', '"Block" Area Designation Mode'),
        ('ATTR_LIN', '"Line" Area Designation Mode'),
        ('ATTR_DIV', '"Divide" Area Designation Mode'),
        ('ATTR_CHR', '"1CHR" Area Designation Mode'),
        ('SOUND', 'Sound On/Off'),
        ('SOU_TRN', 'Transfer Sound PRG/DATA'),
        ('PAL_SET', 'Set SGB Palette Indirect'),
        ('PAL_TRN', 'Set System Color Palette Data'),
        ('ATRC_EN', 'Enable/disable Attraction Mode'),
        ('TEST_EN', 'Speed Function'),
        ('ICON_EN', 'SGB Function'),
        ('DATA_SND', 'SUPER NES WRAM Transfer 1'),
        ('DATA_TRN', 'SUPER NES WRAM Transfer 2'),
        ('MLT_REG', 'Controller 2 Request'),
        ('JUMP', 'Set SNES Program Counter'),
        ('CHR_TRN', 'Transfer Character Font Data'),
        ('PCT_TRN', 'Set Screen Data Color Data'),
        ('ATTR_TRN', 'Set Attribute from ATF'),
        ('ATTR_SET', 'Set Data to ATF'),
        ('MASK_EN', 'Game Boy Window Mask'),
        ('OBJ_TRN', 'Super NES OBJ Mode'),
    ]

    def __init__(self, address: Address):
        super().__init__(address, 16)
        self.command_code = -1
        self.packets = 1

    def load_from_rom(self, rom: 'ROMBytes'):
        start = self.address.rom_file_offset
        command_byte = rom[start]
        self.command_code, self.packets = divmod(command_byte, 8)
        self.size = 16 * self.packets
        self.bytes = rom[start: start + self.size]

    @property
    def description(self):
        if not 0 <= self.command_code < len(self.COMMANDS):
            return "Unknown"
        name, explanation = self.COMMANDS[self.command_code]
        return f"${self.command_code:02x} {name} ({explanation})"

    @property
    def create_cmd(self):
        return ('data', 'create', 'sgb', self.address)


class CartridgeHeader(BaseData):
    description = "Cartridge Header"

    def __init__(self):
        super().__init__(Address.from_rom_offset(0x104), 0x4c)

    @property
    def metadata(self):
        return HeaderDecoder(self.bytes)

    def load_from_rom(self, rom: 'ROMBytes'):
        self.bytes = rom[0x100:0x150]

    @property
    def create_cmd(self):
        return ('data', 'create', 'header')


class EmptyData(BaseData):
    description = "Empty"

    def __init__(self, address: Address, size: int = 0):
        super().__init__(address, size)

    def load_from_rom(self, rom: 'ROMBytes'):
        if not self.size:
            pos = start = self.address.rom_file_offset
            end = self.address.zone_end.rom_file_offset
            while pos <= end:
                # Special case to exclude the NOP at the entry point
                if rom[pos] != 0 or pos == 0x100:
                    break
                pos += 1
            self.size = pos - start

        self.bytes = bytes(self.size)

    @property
    def create_cmd(self):
        return ('data', 'create', 'empty', self.address, self.size)


class DataManager(AsmManager):

    def __init__(self, disassembler: 'Disassembler'):
        super().__init__(disassembler)

        self.inventory: Dict[Address, BaseData] = {}
        self._blocks_map: AddressMapping[int] = AddressMapping()

    def reset(self):
        self.inventory.clear()
        self._blocks_map.clear()

    def create(self, address: Address, size: int):
        self._insert(BinaryData(address, size))

    def create_table(self, address: Address, rows: int, structure: List[RowType]):
        self._insert(DataTable(address, rows, structure))

    def create_palette(self, address: Address, rows: int):
        self._insert(PaletteData(address, rows))

    def create_rle(self, address: Address):
        self._insert(RLEDataBlock(address))

    def create_interlaced_rle(self, address: Address, size: int):
        self._insert(InterlacedRLEDataBlock(address, size))

    def create_jumptable(self, address: Address, rows: int = 0):
        self._insert(JumpTable(address, rows))

    def create_empty(self, address: Address, size: int = 0):
        self._insert(EmptyData(address, size))

    def create_header(self):
        self._insert(CartridgeHeader())

    def create_sgb(self, address: Address):
        self._insert(SGBPacket(address))

    def delete(self, address: Address):
        if address not in self.inventory:
            raise IndexError(address)
        del self.inventory[address]
        del self._blocks_map[address]

    def _insert(self, data: BaseData):
        data.load_from_rom(self.asm.rom)

        prev_blk = self.get_data(data.address)
        if prev_blk and prev_blk.end_address > data.address:
            raise ValueError("Data overlap detected")

        next_blk = self.next_block(data.address)
        if next_blk and next_blk.address < data.end_address:
            raise ValueError("Data overlap detected")

        self.inventory[data.address] = data
        self._blocks_map[data.address] = data.size

    def next_block(self, address) -> Optional[BaseData]:
        try:
            addr, _ = self._blocks_map.get_ge(address)
        except LookupError:
            return None
        return self.inventory[addr]

    def get_data(self, address) -> Optional[BaseData]:
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

        @data_cli.group('create')
        def data_create():
            pass

        @data_create.command('simple')
        @click.argument('address', type=address_arg)
        @click.argument('size', type=ExtendedInt())
        def data_create_simple(address: Address, size):
            self.create(address, size)

        @data_create.command('table')
        @click.argument('address', type=address_arg)
        @click.argument('rows', type=ExtendedInt())
        @click.argument('structure', type=str)
        def data_create_table(address: Address, rows: int, structure: str):
            struct = [TYPES_BY_NAME[item] for item in structure.split(',')]
            self.create_table(address, rows, struct)

        @data_create.command('palette')
        @click.argument('address', type=address_arg)
        @click.argument('rows', type=int, default=8)
        def data_create_palette(address, rows):
            self.create_palette(address, rows)

        @data_create.command('rle')
        @click.argument('address', type=address_arg)
        def data_create_rle(address: Address):
            self.create_rle(address)

        @data_create.command('interlaced_rle')
        @click.argument('address', type=address_arg)
        @click.argument('size', type=ExtendedInt())
        def data_create_interlaced_rle(address: Address, size: int):
            self.create_interlaced_rle(address, size)

        @data_create.command('jumptable')
        @click.argument('address', type=address_arg)
        @click.argument('rows', type=ExtendedInt(), default=0)
        def data_create_jumptable(address: Address, rows: int = 0):
            self.create_jumptable(address, rows)

        @data_create.command('sgb')
        @click.argument('address', type=address_arg)
        def data_create_sgb(address: Address):
            self.create_sgb(address)

        @data_create.command('empty')
        @click.argument('address', type=address_arg)
        @click.argument('size', type=int, default=0)
        def data_create_empty(address: Address, size: int):
            self.create_empty(address, size)

        @data_create.command('header')
        def data_create_header():
            self.create_header()

        @data_cli.command('delete')
        @click.argument('address', type=address_arg)
        def data_delete(address: Address):
            self.delete(address)

        return data_cli

    def build_cli_v2(self) -> 'UgbCommandGroup':
        data_create = UgbCommandGroup(self.asm, "create")
        data_create.add_command("empty", self.create_empty)
        data_create.add_command("header", self.create_header)
        data_create.add_command("interlaced_rle", self.create_interlaced_rle)
        data_create.add_command("jumptable", self.create_jumptable)
        data_create.add_command("palette", self.create_palette)
        data_create.add_command("rle", self.create_rle)
        data_create.add_command("sgb", self.create_sgb)
        data_create.add_command("simple", self.create)

        @data_create.add_command("table")
        def data_create_table(address: Address, rows: int, structure: str):
            struct = [TYPES_BY_NAME[item] for item in structure.split(',')]
            self.create_table(address, rows, struct)

        data_cli = UgbCommandGroup(self.asm, "data")
        data_cli.add_group(data_create)
        data_cli.add_command("delete", self.delete)

        return data_cli

    def save_items(self):
        for addr in sorted(self.inventory):
            yield self.inventory[addr].create_cmd
