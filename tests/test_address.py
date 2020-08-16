
from hypothesis import given, strategies as st

from ungameboy.address import Address, MemoryType, MemoryZone


memory_zones = st.builds(
    MemoryZone,
    type=st.sampled_from(MemoryType),
    bank=st.integers(min_value=0, max_value=0x1FF),
)


@st.composite
def addresses(draw):
    zone = draw(memory_zones)
    offset = draw(st.integers(min_value=0, max_value=zone.type.size - 1))
    return Address(zone, offset)


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
