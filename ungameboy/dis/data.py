from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Tuple, Type, Union

from .manager_base import AsmManager
from ..address import Address
from ..data_structures import AddressMapping
from ..data_types import Byte, CgbColor, Word

if TYPE_CHECKING:
    from .disassembler import Disassembler
    from .decoder import ROMBytes
    from ..commands import UgbCommandGroup

RowItem = Union[Byte, CgbColor, Word, Address]


@dataclass(frozen=True)
class RowType:
    name: str
    type: Callable[[int], 'RowItem']
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

DATA_TYPES: Dict[str, 'Data'] = {}
PROCESSORS: Dict[str, Type['DataProcessor']] = {}


# Built-in data processors

class DataProcessorMeta(ABCMeta):
    name = ""

    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if not cls.name:
            raise TypeError("DataProcessor sub-classes must define a slug")
        # noinspection PyTypeChecker
        PROCESSORS[cls.name] = cls


class DataProcessor(metaclass=DataProcessorMeta):
    name = "default"

    @abstractmethod
    def process(self, rom: 'ROMBytes', address: Address) -> Tuple[bytes, int]:
        return b'', 0

    @classmethod
    def parse(cls, command: str) -> 'DataProcessor':
        name, _, args = command.partition(":")
        proc = PROCESSORS[name]
        return proc.load(args)

    @classmethod
    def load(cls, args: str):
        if args:
            raise ValueError("No arguments expected")
        return cls()

    def dump(self):
        return self.name


class JumpTableDetector(DataProcessor):
    name = "jumptable"

    def process(self, rom: 'ROMBytes', address: Address):
        # Auto-detect the table length, assuming it contains the
        # address right after the end of the table.
        rows = 0
        start = address.memory_address
        min_pos = 0xffff

        while (start + rows * 2) < min_pos:
            pos = (address + rows * 2).rom_file_offset
            rows += 1
            row_bin = rom[pos:pos + 2]
            row_pos = int.from_bytes(row_bin, 'little')
            if start < row_pos < min_pos:
                min_pos = row_pos

        if not rows:
            raise ValueError("Failed to detect jump table")

        return b'', rows * 2


# Data classes

class DataMeta(ABCMeta):
    name = ""

    def __init__(cls, name, bases, attrs):
        super().__init__(name, bases, attrs)
        if not cls.name:
            raise TypeError("Data sub-classes must define a name")
        # noinspection PyTypeChecker
        DATA_TYPES[cls.name] = cls


class Data(metaclass=DataMeta):
    name = "basic"
    description = "Data"

    def __init__(
            self,
            address: Address,
            size: int = 0,
            processor: Optional[DataProcessor] = None,
            row_size: int = 8,
    ):
        self.address = address
        self.size = size
        self.processor = processor
        self.row_size = row_size

        self.rom_bytes = b''
        self.data_bytes = b''

    @staticmethod
    def parse(address, size, command, processor) -> 'Data':
        name, _, args = command.partition(":")
        data_cls = DATA_TYPES[name or "basic"]
        return data_cls.load(address, size, args, processor)

    @classmethod
    def load(
            cls,
            address: Address,
            size: int,
            args: str,
            processor: Optional[DataProcessor],
    ) -> 'Data':
        if args:
            raise ValueError("No arguments expected")
        return cls(address, size, processor)

    def save(self):
        cmd = ('data', 'load', self.address, self.size)
        if self.name != "basic":
            cmd += (self.type_repr,)
        if self.data_bytes and self.processor is not None:
            cmd += ("--processor", self.processor.dump())
        return cmd

    @property
    def next_address(self) -> Address:
        return self.address + self.size

    @property
    def data(self) -> bytes:
        return self.data_bytes or self.rom_bytes

    def populate(self, rom: 'ROMBytes'):
        proc = self.processor
        if proc is not None:
            self.data_bytes, self.size = proc.process(rom, self.address)

        pos = self.address.rom_file_offset
        self.rom_bytes = rom[pos:pos + self.size]

    @property
    def rows(self) -> int:
        return 1 + (self.size - 1) // self.row_size

    def get_row_bin(self, row: int) -> bytes:
        n_rows = 1 + (self.size - 1) // self.row_size
        if not 0 <= row < n_rows:
            raise IndexError("Row index out of range")
        return self.rom_bytes[self.row_size * row:self.row_size * (row + 1)]

    def get_row(self, row: int) -> List[RowItem]:
        return [Byte(b) for b in self.get_row_bin(row)]

    @property
    def type_repr(self) -> str:
        return self.name


class EmptyData(Data):
    name = "empty"
    description = "Empty Space"

    def populate(self, rom: 'ROMBytes'):
        if self.size <= 0:
            pos = start = self.address.rom_file_offset
            end = self.address.zone_end.rom_file_offset
            while pos <= end:
                # Special case to exclude the NOP at the entry point
                if rom[pos] != 0 or pos == 0x100:
                    break
                pos += 1
            self.size = pos - start
        self.rom_bytes = bytes(self.size)


class CartridgeHeader(Data):
    name = "header"
    description = "Cartridge Header"

    def populate(self, rom: 'ROMBytes'):
        if self.address.rom_file_offset != 0x104:
            raise ValueError("Cartridge header can only be at $0104")
        self.size = 0x4c
        self.data_bytes = rom[0x100:0x150]
        self.rom_bytes = rom[0x104:0x150]


class SGBPacket(Data):
    name = "sgb"

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

    @property
    def description(self) -> str:
        command_code = self.data[0] // 8
        if not 0 <= command_code < len(self.COMMANDS):
            return "Unknown"
        name, explanation = self.COMMANDS[command_code]
        return f"SGB Packet: ${command_code:02x} {name} ({explanation})"

    def populate(self, rom: 'ROMBytes'):
        self.size = 16 * (rom[self.address.rom_file_offset] & 0b111)
        super().populate(rom)


class DataTable(Data):
    name = "table"

    def __init__(
            self,
            address: Address,
            rows: int,
            row_struct: List[RowType],
            processor: Optional[DataProcessor] = None,
    ):
        row_size = self.calc_row_size(row_struct)
        self.row_struct = row_struct
        super().__init__(address, rows * row_size, processor, row_size)

    @classmethod
    def load(
            cls,
            address: Address,
            size: int,
            args: str,
            processor: Optional[DataProcessor],
    ) -> 'Data':
        struct = [TYPES_BY_NAME[item] for item in args.split(',')]
        rows, rem = divmod(size, sum(item.n_bytes for item in struct))
        if rem:
            raise ValueError()
        return cls(address, rows, struct)

    @property
    def type_repr(self) -> str:
        row_str = ','.join(item.name for item in self.row_struct)
        return f"{self.name}:{row_str}"

    @property
    def description(self) -> str:
        row_str = ','.join(item.name for item in self.row_struct)
        return f"Table: {self.rows} \u00d7 {row_str}"

    @classmethod
    def calc_row_size(cls, struct: List[RowType]):
        return sum(item.n_bytes for item in struct)

    def get_row(self, row: int) -> List[RowItem]:
        row_bytes = self.get_row_bin(row)
        row_values, pos = [], 0

        for t in self.row_struct:
            value = int.from_bytes(row_bytes[pos:pos + t.n_bytes], t.endian)
            row_values.append(t.type(value))
            pos += t.n_bytes

        return row_values


class Jumptable(DataTable):
    name = "jumptable"

    def __init__(self, address: Address, rows: int = 0):
        struct = [TYPES_BY_NAME['addr']]
        proc = JumpTableDetector() if rows <= 0 else None
        super().__init__(address, rows, struct, proc)

    @classmethod
    def load(cls, address, size, args, processor) -> 'Data':
        rows, rem = divmod(size, 2)
        if rem:
            raise ValueError()
        return cls(address, rows)

    @property
    def type_repr(self) -> str:
        return self.name

    @property
    def description(self) -> str:
        return f"Jumptable: {self.rows} \u00d7 Address"


# Manager

class DataManager(AsmManager):

    def __init__(self, asm: 'Disassembler'):
        super().__init__(asm)
        self.inventory: Dict[Address, Data] = {}
        self._blocks_map: AddressMapping[int] = AddressMapping()

    def reset(self):
        self.inventory.clear()
        self._blocks_map.clear()

    def insert(self, data: Data, initial=False):
        data.populate(self.asm.rom)

        if not data.size and data.rom_bytes:
            raise ValueError("Cannot create empty data")

        prev_blk = self.get_data(data.address)
        if prev_blk and prev_blk.next_address > data.address:
            raise ValueError("Data overlap detected")

        next_blk = self.next_block(data.address)
        if next_blk and next_blk.address < data.next_address:
            raise ValueError("Data overlap detected")

        self.inventory[data.address] = data
        self._blocks_map[data.address] = data.size

        if not initial:
            self.asm.xrefs.index_data(data.address)

    def create_basic(
            self, address: Address, size: int, processor: DataProcessor = None
    ):
        self.insert(Data(address, size, processor))

    def create_table(self, address: Address, rows: int, structure: List[RowType]):
        self.insert(DataTable(address, rows, structure))

    def create_palette(self, address: Address, rows: int):
        color_type = TYPES_BY_NAME['color']
        self.insert(DataTable(address, rows, [color_type] * 4))

    def create_jumptable(self, address: Address, rows: int = 0):
        self.insert(Jumptable(address, rows))

    def create_empty(self, address: Address, size: int = 0):
        self.insert(EmptyData(address, size))

    def create_header(self):
        self.insert(CartridgeHeader(Address.from_rom_offset(0x104)))

    def create_sgb(self, address: Address):
        self.insert(SGBPacket(address))

    def delete(self, address: Address):
        if address not in self.inventory:
            raise IndexError(address)
        del self.inventory[address]
        del self._blocks_map[address]

    def load(
            self,
            address: Address,
            size: int,
            data_type: str = "",
            processor: DataProcessor = None,
    ):
        data = Data.parse(address, size, data_type, processor)
        self.insert(data, initial=True)

    def next_block(self, address: Address) -> Optional[Data]:
        try:
            addr, _ = self._blocks_map.get_ge(address)
        except LookupError:
            return None
        return self.inventory[addr]

    def get_data(self, address: Address) -> Optional[Data]:
        try:
            addr, size = self._blocks_map.get_le(address)
        except LookupError:
            return None
        if address >= addr + size:
            return None
        return self.inventory[addr]

    def build_cli_v2(self) -> 'UgbCommandGroup':
        from ..commands import UgbCommandGroup

        data_create = UgbCommandGroup(self.asm, "create")
        data_create.add_command("basic", self.create_basic)
        data_create.add_command("empty", self.create_empty)
        data_create.add_command("header", self.create_header)
        data_create.add_command("jumptable", self.create_jumptable)
        data_create.add_command("palette", self.create_palette)
        data_create.add_command("sgb", self.create_sgb)

        @data_create.add_command("table")
        def data_create_table(address: Address, rows: int, structure: str):
            struct = [TYPES_BY_NAME[item] for item in structure.split(',')]
            self.create_table(address, rows, struct)

        data_cli = UgbCommandGroup(self.asm, "data")
        data_cli.add_group(data_create)
        data_cli.add_command("delete", self.delete)
        data_cli.add_command("load", self.load)
        return data_cli

    def save_items(self):
        for addr in sorted(self.inventory):
            yield self.inventory[addr].save()
