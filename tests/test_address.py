
from hypothesis import given, strategies as st

from ungameboy.address import BANKS, Address, MemoryType


@st.composite
def addresses(draw):
    mem_type = draw(st.sampled_from(MemoryType))

    if mem_type in BANKS:
        max_offset = BANKS[mem_type] or mem_type.size
        mem_bank = draw(st.integers(min_value=0, max_value=511))
    else:
        max_offset = mem_type.size
        mem_bank = 0

    offset = draw(st.integers(min_value=0, max_value=max_offset - 1))
    return Address(mem_type, mem_bank, offset)


@given(st.integers(min_value=0))
def test_address_rom_offset(offset):
    address = Address.from_rom_offset(offset)
    assert address.rom_file_offset == offset
    assert 0 <= address.memory_address < 0x8000


@given(st.integers(min_value=0, max_value=0xFFFF))
def test_address_mem_offset(mem_address):
    address = Address.from_memory_address(mem_address)
    assert address.memory_address == mem_address


@given(addresses())
def test_parse_address(address):
    assert Address.parse(str(address)) == address
