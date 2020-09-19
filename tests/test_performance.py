from ungameboy.dis import Disassembler
from ungameboy.project_save import load_project
from ungameboy.prompt.control import AsmControl


if __name__ == '__main__':
    import sys
    asm = Disassembler()
    asm.project_name = sys.argv[1]
    load_project(asm)
    ctrl = AsmControl(asm)
