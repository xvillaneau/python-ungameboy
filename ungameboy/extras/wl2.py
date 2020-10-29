from bisect import bisect_right
from typing import TYPE_CHECKING, List

from ..address import Address
from ..data_types import Byte, SignedByte
from ..dis.data import Data, DataProcessor, DataTable, JumpTableDetector, RowItem
from ..scripts import asm_script

if TYPE_CHECKING:
    from ..dis import Disassembler, ROMBytes


class RunLengthEncodingProcessor(DataProcessor):
    name = "wl2.rle"

    def process(self, rom: 'ROMBytes', address: Address):
        data = []
        start_pos = pos = address.rom_file_offset

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

        return bytes(data), pos - start_pos + 1


class InterlacedRLEProcessor(DataProcessor):
    name = "wl2.rlei"

    def __init__(self, data_size: int):
        self.data_size = data_size

    def dump(self):
        return f"{self.name}:{self.data_size}"

    @classmethod
    def load(cls, args: str):
        size = int(args)
        return cls(size)

    def process(self, rom: 'ROMBytes', address: Address):
        data = []
        start_pos = pos = address.rom_file_offset
        byte = rom[pos]
        while byte != 0:
            pos += 1
            pkg_type, arg = divmod(byte, 0x80)
            remaining = self.data_size - len(data)

            if pkg_type > 0:  # Data
                packet = rom[pos:pos + arg]
                pos += min(arg, remaining)
            else:  # RLE
                packet = [rom[pos]] * arg
                pos += 1
            data.extend(packet[:remaining])

            if len(data) == self.data_size:
                break
            byte = rom[pos]
        else:
            pos += 1

        half = self.data_size // 2
        data = [
            data[i // 2 + half * (i % 2)]
            for i in range(self.data_size)
        ]

        return bytes(data), pos - start_pos


class WL2Sprite(Data):
    name = "wl2.sprite"

    def __init__(self, address: Address, size: int = 0):
        super().__init__(address, size)
        self.row_size = 4

    def populate(self, rom: 'ROMBytes'):

        if not self.size:
            start, offset = self.address.rom_file_offset, 0
            while rom[start + offset] != 0x80:
                offset += 4
            self.size = offset + 1

        super().populate(rom)
        if self.rom_bytes[-1] != 0x80:
            raise ValueError("Sprite data must end with $80")

    def save(self):
        return ('data', 'load', self.address, self.size, self.name)

    @classmethod
    def load(cls, address, size, args, processor) -> 'Data':
        return cls(address, size)

    def get_row_items(self, row: int):
        row_bin = self.get_row_bin(row)
        if row_bin == b'\x80':
            return [Byte(0x80)]
        x, y, n, f = row_bin
        return [SignedByte(x), SignedByte(y), Byte(n), Byte(f)]


@asm_script("wl2.sprites_table")
def detect_sprites_table(asm: 'Disassembler', address: Address):
    table = DataTable(address, 0, 'addr', JumpTableDetector())
    asm.data.insert(table)

    asm.labels.auto_create(address)

    visited = set()
    for row in table:
        ref = asm.context.detect_addr_bank(address, row.items[0])
        if ref in visited:
            continue
        visited.add(ref)

        asm.data.insert(WL2Sprite(ref))
        asm.labels.auto_create(ref, local=True)


class WL2SoundTrackIndex(Data):
    name = "wl2.track_index"

    def __init__(self, address: Address, size: int = 0, processor=None):
        super().__init__(address, size, processor)
        self.row_size = 2
        self.voices = []
        self.extras = []

    def populate(self, rom: 'ROMBytes'):
        n_voices = rom[self.address.rom_file_offset]
        n_extra = rom[self.address.rom_file_offset + 1]
        bank = self.address.bank

        offset = self.address.rom_file_offset + 2
        for i in range(n_voices * (1 + n_extra)):
            addr = int.from_bytes(rom[offset:offset+2], "little")
            addr = Address.from_memory_address(addr, bank)
            offset += 2
            if addr.zone != self.address.zone:
                break
            if i < n_voices:
                self.voices.append(addr)
            else:
                self.extras.append(addr)

        self.size = 2 * (1 + len(self.voices) + len(self.extras))
        super().populate(rom)

    def get_row_items(self, row: int) -> List[RowItem]:
        row_bin = self.get_row_bin(row)
        if row == 0:
            return [Byte(b) for b in row_bin]
        else:
            addr = int.from_bytes(row_bin, "little")
            return [Address.from_memory_address(addr, self.address.bank)]


class WL2SoundVoice(Data):
    name = "wl2.voice"

    RESET_CODES = frozenset([0xb1, *range(0xb6, 0xbc), 0xc7, 0xc8, 0xcb, 0xcc])
    DATA_CODES = frozenset([0xb5, *range(0xbc, 0xc7), 0xc9, 0xca])
    ADDR_CODES = frozenset([0xb2, 0xb3])

    def __init__(self, address: Address, size: int = 0, processor=None):
        super().__init__(address, size, processor)
        self.map: List[int] = []

    def populate(self, rom: 'ROMBytes'):
        start = offset = self.address.rom_file_offset
        stored_code = 0

        def process_code(fallback=False):
            nonlocal offset, stored_code

            if fallback:
                code = stored_code
            else:
                code = rom[offset]
                offset += 1
            if code >= 0xbe:
                stored_code = code

            if code in self.RESET_CODES:
                return False
            if not fallback and code < 0x80:
                offset -= 1
                return process_code(fallback=True)

            if code == 0xcd:  # Jumptable 1
                arg = rom[offset]
                offset += 1
                return arg in (*range(1, 8), 0xa, 0xb)

            if code <= 0xb0 or code == 0xb4:
                pass
            elif code in self.DATA_CODES:
                offset += 1
            elif code in self.ADDR_CODES:
                offset += 2
            elif code == 0xcf:
                arg = rom[offset]
                offset += 0x24 <= arg < 0x80
            else:
                # Remaining: code >= 0xd0 and code == 0xce
                arg = rom[offset]
                while arg < 0x80:
                    offset += 1
                    arg = rom[offset]

            return True

        self.map.clear()
        self.map.append(0)
        while process_code():
            self.map.append(offset - start)

        self.size = offset - start
        super().populate(rom)

    @property
    def rows(self) -> int:
        return len(self.map)

    def row_at(self, address: Address) -> int:
        if address.zone != self.address.zone:
            raise IndexError("Address not in same zone")
        offset = address.offset - self.address.offset
        if not 0 <= offset < self.size:
            raise IndexError("Address not in data")
        return bisect_right(self.map, offset) - 1

    def row_address(self, row: int) -> Address:
        return self.address + self.map[row]

    def get_row_bin(self, row: int) -> bytes:
        start = self.map[row]
        end = self.size if row >= self.rows - 1 else self.map[row + 1]
        return self.data[start:end]

    def get_row_items(self, row: int) -> List[RowItem]:
        row_bin = self.get_row_bin(row)
        code = row_bin[0]

        if code == 0xb4:
            return ["pop"]

        if code in self.ADDR_CODES:
            addr = int.from_bytes(row_bin[1:3], "little")
            addr = Address.from_memory_address(addr)
            name = "jump" if code == 0xb2 else "push+jump"
            return [name, addr]

        if code == 0x80:
            return ["noop"]

        if 0x81 <= code <= 0xb0:
            index = code - 0x81
            if index < 0x18:
                cycles = index + 1
            else:
                a, b = divmod(index - 0x18, 4)
                cycles = 0x1c + 0xc * a + 2 * (b + (b == 3))
            return [f"wait {cycles} cycle{'s' * (cycles != 1)}"]

        return [Byte(b) for b in row_bin]


@asm_script("wl2.track")
def detect_audio_track(asm: 'Disassembler', address: Address):
    index = WL2SoundTrackIndex(address)
    asm.data.insert(index)

    for voice_addr in index.voices:
        asm.data.insert(WL2SoundVoice(voice_addr))

    asm.labels.auto_create(min(index.voices))
    for i, voice_addr in enumerate(index.voices, start=1):
        asm.labels.create(voice_addr, f".voice_{i}")
    for extra_addr in index.extras:
        asm.labels.auto_create(extra_addr, local=True)
    asm.labels.create(address, ".index")
