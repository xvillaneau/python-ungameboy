from io import BytesIO

from hypothesis import given, strategies as st
import pytest

from ungameboy.disassembler import Disassembler, ROMView
from ungameboy.prompt.control import AsmControl

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
    asm = Disassembler()
    asm.load_rom(BytesIO(EXAMPLE_CODE))
    control = AsmControl(ROMView(asm))
    control.height = 5
    control.refresh()

    # ROM is short enough for everything to be loaded
    assert control.start_index == 0
    assert control.end_index == len(asm.rom)


def test_empty_buffer():
    asm = Disassembler()
    control = AsmControl(ROMView(asm))

    assert control.start_index == 0
    assert control.end_index == 0


@given(st.binary(min_size=16, max_size=32768), st.lists(st.integers()))
def test_random_binary(binary, moves):
    asm = Disassembler()
    asm.load_rom(BytesIO(binary))
    control = AsmControl(ROMView(asm))
    control.height = 5
    control.refresh()

    assert control.start_index == 0
    assert control.scroll_index == 0
    assert control.scroll_pos == 0

    control.move_down(1000)

    for move in moves:
        assert len(control) <= control.bs * 2
        if move < 0:
            control.move_up(-move)
        else:
            control.move_down(move)
