import os

from ungameboy.disassembler import Disassembler
from ungameboy.project_save import load_project
from ungameboy.prompt.control import AsmControlV2


def test_control_v2():
    asm = Disassembler()
    asm.project_name = os.getenv('UGB_TEST_PROJECT')
    load_project(asm)

    ctrl = AsmControlV2(asm)
    ctrl.refresh()
    print(ctrl.lines_count)
    print(len(ctrl.lines_map))


if __name__ == '__main__':
    test_control_v2()
