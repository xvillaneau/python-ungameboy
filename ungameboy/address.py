"""
Address abstraction layer and tools.

The code in here helps with one of the fundamental challenges of the
whole project (and one of the few areas where radare2 fall short):
there is more than one address space to worry about!

To be more specific, those address spaces are:
- The offset of any given byte in the ROM dump, our input data
- The 16-bit address space accessible to the CPU, of which the first
  half exposes the ROM and the other half holds RAM of all sorts.

Those address spaces overlap in odd ways, in particular thanks to the
ROM bank system: the $0000-$3FFF space permanently exposes the first
16KiB of the ROM (a.k.a. ROM0) and the $4000-$7FFF space can expose any
other 16KiB segment of the ROM (the banks). Banking also exists for the
Video, Work, and External RAM ranges, depending on the hardware and the
MBC chip in the cartridge.

This means that when the code reads ``call $441a``, it is critical to
know which ROM bank is loaded to find the code being run. For another
example, ``ld a, [$cd1f]`` refers to a register in RAM and not to the
$cd1f offset in ROM.

So this is what the `Address` data structure is meant for. It represents
what I call a "Global Address", an unambiguous abstract address that can
be passed around, and converted into other spaces where needed.
"""

from enum import Enum
from functools import total_ordering
import re
from typing import NamedTuple, Optional

from .data_types import SignedByte

__all__ = [
    'MemoryType', 'MemoryZone', 'Address',
    'ROM', 'VRAM', 'SRAM', 'WRAM', 'OAM', 'IOR', 'HRAM',
    'ROM0', 'ROM_',
]


@total_ordering
class MemoryType(Enum):
    ROM = ("ROM", 0x0000, 0x8000)
    VRAM = ("VRAM", 0x8000, 0x2000)
    SRAM = ("SRAM", 0xA000, 0x2000)
    WRAM = ("WRAM", 0xC000, 0x2000)
    ECHO = ("ECHO", 0xE000, 0x1E00)
    OAM = ("OAM", 0xFE00, 0xA0)
    BAD = ("BAD", 0xFEA0, 0x60)
    IOR = ("IOR", 0xFF00, 0x80)
    HRAM = ("HRAM", 0xFF80, 0x80)

    def __new__(cls, value: str, offset: int, size: int):
        order = len(cls.__members__)
        obj = object.__new__(cls)
        obj._value_ = value
        obj._order = order
        obj.offset = offset
        obj.size = size
        return obj

    @property
    def end(self):
        return self.offset + self.size

    def __gt__(self, other):
        if not isinstance(other, MemoryType):
            return NotImplemented
        return self._order > other._order


ROM, VRAM, SRAM, WRAM, _, OAM, _, IOR, HRAM = MemoryType

# Specification of the available banks (max specs at least)
# The first element is the offset in that section at which the banked
# memory starts, and the second is the max # of banks.
# TODO: Make this logic aware of the cartridge type
BANKS = {
    ROM: (0x4000, 512),
    # VRAM: (0, 2),
    # SRAM: (0, 16),
    # WRAM: (0, 4),
}


class MemoryZone(NamedTuple):
    type: MemoryType
    bank: int = 0

    def __repr__(self):
        if self.bank < 0:
            return str(self.type.value)
        return f"{self.type.value}{self.bank:x}"

    def __contains__(self, item):
        if isinstance(item, Address):
            if item.zone is not self:
                return False
            return 0 <= item.offset < self.type.size
        if isinstance(item, int):
            return Address.from_memory_address(item) in self
        return False


ROM0 = MemoryZone(ROM, 0)
ROM_ = MemoryZone(ROM, -1)


class Address(NamedTuple):
    zone: MemoryZone
    offset: int

    _addr_re = re.compile(
        r"""
        (?:
          0x | \$ |        # For mem addresses, hex prefix compulsory
          (?:
            ([a-z]{3,4})?  # Mem type optional, defaults to ROM
            ([0-9a-f]+)    # Mem bank compulsory
            :
          )
        )
        ([0-9a-f]{,4})      # Address offset limited to $FFFF
        """,
        flags=re.IGNORECASE | re.VERBOSE,
    )

    @classmethod
    def parse(cls, address: str) -> "Address":
        match = cls._addr_re.fullmatch(address)
        if match is None:
            raise ValueError(f"Invalid address: {address}")

        m_type, m_bank, offset = match.groups()

        offset = int(offset, base=16)
        if m_bank is None:
            return cls.from_memory_address(offset)

        m_bank = int(m_bank, base=16)
        m_type = ROM if m_type is None else MemoryType(m_type.upper())

        offset -= m_type.offset
        if m_type in BANKS and m_bank > 0:
            offset -= BANKS[m_type][0]

        return Address(MemoryZone(m_type, m_bank), offset)

    @classmethod
    def from_rom_offset(cls, offset: int) -> "Address":
        bank, offset = divmod(offset, 0x4000)
        return Address(MemoryZone(ROM, bank), offset)

    @classmethod
    def from_memory_address(cls, address: int) -> "Address":
        zone_type = next(
            (t for t in MemoryType if t.offset <= address < t.end),
            None,
        )
        if zone_type is None:
            raise ValueError(f"Invalid RAM address {address:x}")

        offset = address - zone_type.offset
        if zone_type in BANKS:
            bank_start, _ = BANKS[zone_type]
            bank_num = 0 if offset < bank_start else -1
        else:
            bank_num = -1

        return Address(MemoryZone(zone_type, bank_num), offset)

    @property
    def rom_file_offset(self) -> Optional[int]:
        if self.zone.type is not ROM:
            return None
        return 0x4000 * self.zone.bank + self.offset

    @property
    def memory_address(self) -> int:
        offset = self.offset + self.zone.type.offset
        if self.zone.type in BANKS and self.zone.bank > 0:
            offset += BANKS[self.zone.type][0]
        return offset

    @property
    def is_valid(self) -> bool:
        return self in self.zone

    def __repr__(self):
        return f"{self.zone}:{self.memory_address:04x}"

    def __add__(self, other) -> "Address":
        if isinstance(other, SignedByte):
            other = other if other < 0x80 else (other - 256)
        if isinstance(other, int):
            return Address(self.zone, self.offset + other)
        return NotImplemented

    def __sub__(self, other) -> "Address":
        if isinstance(other, int):
            return self + (-other)
        return NotImplemented
