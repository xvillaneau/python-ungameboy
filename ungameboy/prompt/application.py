from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import merge_key_bindings
from prompt_toolkit.styles import Style

from .key_bindings import load_buffer_bindings, load_layout_bindings
from .layout import UGBLayout
from .prompt import UGBPrompt
from ..disassembler import Disassembler


UGB_STYLE = {
    'ugb.address': 'fg:green',
    'ugb.bin': 'fg:#aaaaaa',
    'ugb.instr.op': 'fg:ansiyellow',
    'ugb.instr.reg': 'fg:ansibrightblue',
    'ugb.instr.cond': 'fg:ansicyan',
    'ugb.instr.value': 'fg:ansibrightyellow',
    'ugb.instr.op.nop': 'fg:ansiblue',
    'ugb.instr.op.ret': 'fg:ansired bold',
    'ugb.instr.op.reti': 'fg:ansired bold',
    'ugb.instr.op.call': 'fg:ansibrightgreen bold',
    'ugb.instr.op.rst': 'fg:ansibrightgreen bold',
    'ugb.instr.op.jp': 'fg:ansigreen bold',
    'ugb.instr.op.jr': 'fg:ansigreen bold',
    'ugb.instr.op.ld': 'fg:ansibrightmagenta',
    'ugb.instr.op.ldh': 'fg:ansibrightmagenta',
    'ugb.instr.op.ldi': 'fg:ansibrightmagenta',
    'ugb.instr.op.ldd': 'fg:ansibrightmagenta',
    'ugb.instr.op.pop': 'fg:ansibrightcyan bold',
    'ugb.instr.op.push': 'fg:ansibrightcyan bold',
    'ugb.instr.op.invalid': 'fg:ansired',
}


class DisassemblyEditor:

    def __init__(self, asm: Disassembler):
        self.disassembler = asm
        self.prompt_active = False

        self.prompt = UGBPrompt(self)
        self.layout = UGBLayout(self)

        self.app = Application(
            layout=self.layout.layout,
            style=Style.from_dict(UGB_STYLE),
            key_bindings=merge_key_bindings([
                load_layout_bindings(self),
                load_buffer_bindings(self),
            ]),
            full_screen=True,
        )

    def run(self):
        self.app.run()


def run():
    import sys
    from ..project_save import load_project

    asm = Disassembler()

    if len(sys.argv) == 3 and sys.argv[1] == '-p':
        asm.project_name = sys.argv[2]
        load_project(asm)
    elif len(sys.argv) == 1:
        with open(sys.argv[1], 'rb') as rom_file:
            asm.load_rom(rom_file)

    DisassemblyEditor(asm).run()
