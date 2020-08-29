from typing import NamedTuple, Optional

from ..address import Address, ROM

__all__ = ['SpecialLabel']


class SpecialLabel(NamedTuple):
    name: str

    @classmethod
    def detect(cls, address: Address) -> Optional["SpecialLabel"]:
        if address.type is ROM:
            offset = address.memory_address
            if offset < 0x2000:
                return SpecialLabel("SRAM_ENABLE")
            if offset < 0x3000:
                return SpecialLabel("ROM_BANK_L")
            if offset < 0x4000:
                return SpecialLabel("ROM_BANK_9")
            if offset < 0x6000:
                return SpecialLabel("SRAM_BANK")
        return None
