from ungameboy.dis.graphics import zip_bits


class TestZip():
    zipped = bytes.fromhex('0707181f203f407f')
    unzipped = bytes.fromhex('003f03ea0eaa3aaa')
    assert bytes(zip_bits(zipped)) == unzipped
