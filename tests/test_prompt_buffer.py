from io import BytesIO

from hypothesis import given, strategies as st
import pytest

from ungameboy.decoder import ROMBytes
from ungameboy.disassembler import Disassembler
from ungameboy.prompt.buffer import AsmBuffer

EXAMPLE_CODE = bytes.fromhex(
    "cdcb03"    # 00 call $03cb
    "2100fe"    # 03 ld hl, $fe80
    "f081"      # 06 ldh a, [$ff81]
    "c610"      # 08 add a, $10
    "22"        # 0a ldi [hl], a
    "f085"      # 0b ldh a, [$ff85]
    "c608"      # 0d add a, $08
    "22"        # 0f ldi [hl], a
    "78"        # 10 ld a, b
    "22"        # 11 ldi [hl], a
    "79"        # 12 ld a, c
    "22"        # 13 ldi [hl], a
    "f081"      # 14 ldh a, [$ff81]
    "c610"      # 16 add a, $10
    "22"        # 18 ldi [hl], a
    "f085"      # 19 ldh a, [$ff85]
    "c610"      # 1b add a, $10
    "22"        # 1d ldi [hl], a
    "78"        # 1e ld a, b
    "22"        # 1f ldi [hl], a
    "79"        # 20 ld a, c
    "ee60"      # 21 xor a, $60
    "22"        # 23 ldi [hl], a
    "c9"        # 24 ret
)


START_POS = [0, 5, 31, 33]


@pytest.mark.parametrize('start', START_POS)
def test_load(start):
    asm = Disassembler(ROMBytes(BytesIO(EXAMPLE_CODE)))
    buffer = AsmBuffer(asm, address=start, height=5)

    # ROM is short enough for everything to be loaded
    assert buffer.start_address == 0
    assert buffer.end_address == len(asm)
    assert len(buffer.window()) == 5


@given(st.binary(min_size=16, max_size=32768), st.lists(st.integers()))
def test_random_binary(binary, moves):
    asm = Disassembler(ROMBytes(BytesIO(binary)))
    buffer = AsmBuffer(asm, height=5)

    assert buffer.start_address == 0
    assert buffer.scroll_address == 0
    assert buffer.scroll_index == 0

    buffer.move_down(1000)

    for move in moves:
        assert len(buffer) <= buffer.bs * 2
        if move < 0:
            buffer.move_up(-move)
        else:
            buffer.move_down(move)
