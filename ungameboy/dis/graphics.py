from typing import ByteString

ZIPPED = [
    0b00000000, 0b00000001, 0b00000100, 0b00000101,
    0b00010000, 0b00010001, 0b00010100, 0b00010101,
    0b01000000, 0b01000001, 0b01000100, 0b01000101,
    0b01010000, 0b01010001, 0b01010100, 0b01010101,
]


def zip_bits(data: ByteString):
    if len(data) % 2 != 0:
        raise ValueError("Must get an even number of bytes")
    for pos in range(0, len(data), 2):
        lo, hi = data[pos:pos+2]

        yield ZIPPED[lo >> 4] + (ZIPPED[hi >> 4] << 1)
        yield ZIPPED[lo & 15] + (ZIPPED[hi & 15] << 1)


def read_2bpp_values(data: ByteString):
    for zipped in zip_bits(data):
        yield zipped >> 6
        yield (zipped & 0x30) >> 4
        yield (zipped & 0x0c) >> 2
        yield zipped & 0x03
