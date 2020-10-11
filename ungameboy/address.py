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
    'MemoryType', 'Address', 'BANKS',
    'ROM', 'VRAM', 'SRAM', 'WRAM', 'OAM', 'IOR', 'HRAM',
]


@total_ordering
class MemoryType(Enum):
    ROM = ("ROM", 0x0000, 0x8000)
    VRAM = ("VRAM", 0x8000, 0x2000)
    SRAM = ("SRAM", 0xA000, 0x2000)
    WRAM = ("WRAM", 0xC000, 0x2000)
    ECHO = ("ECHO", 0xE000, 0x1E00)
    OAM = ("OAM", 0xFE00, 0xA0)
    RSV = ("RSV", 0xFEA0, 0x60)  # Reserved, cannot be used
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
    ROM: 0x4000,
    VRAM: 0,
    SRAM: 0,
    WRAM: 0x1000,
}


class Address(NamedTuple):
    type: MemoryType
    # Note on banks: -1 means that the bank # is missing.
    bank: int
    offset: int

    _addr_re = re.compile(
        r"""
        (?:
          0x | \$ |        # For mem addresses, hex prefix compulsory
          (?:
            ([A-Z]{3,4})?  # Mem type defaults to ROM, must be uppercase
            \.?            # Optional disambiguation separator
            ([0-9a-f]+)?    # Mem bank, hex lowercase only
            :
          )
        )
        ([0-9a-f]{1,4})      # Address offset limited to $FFFF
        """,
        flags=re.VERBOSE | re.IGNORECASE,
    )

    @classmethod
    def parse(cls, address: str) -> "Address":
        match = cls._addr_re.fullmatch(address)
        if match is None:
            raise ValueError(f"Invalid address: {address}")

        m_type, m_bank, offset = match.groups()

        offset = int(offset, base=16)
        if m_bank is None and m_type is None:
            return cls.from_memory_address(offset)

        m_bank = -1 if m_bank is None else int(m_bank, base=16)
        m_type = ROM if m_type is None else MemoryType(m_type.upper())

        offset -= m_type.offset
        if not 0 <= offset < m_type.size:
            raise ValueError(f"Offset not in range for {m_type.name}")

        bank_start = BANKS.get(m_type)
        if bank_start:  # Not null and > 0
            if m_bank != 0 and offset < bank_start:
                raise ValueError(
                    f"Offset not in the banked {m_type.name}, did you "
                    f"mean {m_type.name}.0:{offset+m_type.offset:04x}?"
                )
            elif m_bank == 0 and offset >= bank_start:
                raise ValueError("Offset too large for bank 0")
            elif m_bank > 0:
                offset -= bank_start

        elif bank_start is None:
            m_bank = 0

        return Address(m_type, m_bank, offset)

    @classmethod
    def from_rom_offset(cls, offset: int) -> "Address":
        bank, offset = divmod(offset, 0x4000)
        return Address(ROM, bank, offset)

    @classmethod
    def from_memory_address(cls, address: int) -> "Address":
        mem_type = next(
            (t for t in MemoryType if t.offset <= address < t.end),
            None,
        )
        if mem_type is None:
            raise ValueError(f"Invalid RAM address {address:x}")

        offset = address - mem_type.offset
        if mem_type in BANKS:
            bank_start = BANKS[mem_type]
            bank = 0
            if offset >= bank_start:
                bank = -1
                offset -= bank_start
        else:
            bank = 0

        return Address(mem_type, bank, offset)

    @property
    def rom_file_offset(self) -> Optional[int]:
        if self.type is not ROM:
            return None
        return 0x4000 * self.bank + self.offset

    @property
    def memory_address(self) -> int:
        offset = self.offset + self.type.offset
        if self.type in BANKS and self.bank != 0:
            offset += BANKS[self.type]
        return offset

    @property
    def zone_end(self) -> "Address":
        if self.type in BANKS:
            bank_start = BANKS[self.type]
            if bank_start == 0:
                zone_size = self.type.size
            elif self.bank == 0:
                zone_size = bank_start
            else:
                zone_size = self.type.size - bank_start
        else:
            zone_size = self.type.size
        return Address(self.type, self.bank, zone_size - 1)

    @property
    def is_valid(self) -> bool:
        if self.bank < 0:
            return False
        size = self.type.size
        if BANKS.get(self.type, 0) > 0:
            bank_start = BANKS[self.type]
            if self.bank > 0:
                size -= bank_start
            else:
                size = bank_start
        return 0 <= self.offset < size

    def __repr__(self):
        if self.type not in BANKS:
            bank_str = ''
        else:
            bank_str = f'.{self.bank:x}' if self.bank >= 0 else '.X'
        return f"{self.type.name}{bank_str}:{self.memory_address:04x}"

    def __add__(self, other) -> "Address":
        if isinstance(other, SignedByte):
            other = other if other < 0x80 else (other - 256)
        if isinstance(other, int):
            return Address(self.type, self.bank, self.offset + other)
        return NotImplemented

    def __sub__(self, other) -> "Address":
        if isinstance(other, int):
            return self + (-other)
        return NotImplemented
