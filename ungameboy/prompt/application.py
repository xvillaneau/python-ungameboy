from itertools import product

from prompt_toolkit.application import Application
from prompt_toolkit.styles import Style

from .filters import UGBFilters
from .gfx_display import GraphicsDisplayState
from .key_bindings import create_global_bindings
from .layout import UGBLayout
from .prompt import UGBPrompt
from .xref_browser import XRefBrowserState
from ..address import Address
from ..dis import Disassembler


UGB_STYLE = {
    'ugb.address': 'fg:#10b020',
    'ugb.address.data': 'fg:#10a080',
    'ugb.bin': 'fg:#aaaaaa',
    'ugb.comment': 'fg:#bbbbbb',
    'ugb.data': 'fg:#55cccc',
    'ugb.data.empty': 'fg:#888888',
    'ugb.data.key': 'fg:#cc6666',
    'ugb.data.value': 'fg:#ebcb4d',
    'ugb.flags': 'fg:#aaaa55',
    'ugb.xrefs': 'fg:#cc5555',
    # Graphics
    'ugb.gfx.pixel.0': 'bg:#ffffff fg:#555555 bold',
    'ugb.gfx.pixel.1': 'bg:#aaaaaa fg:#000000 bold',
    'ugb.gfx.pixel.2': 'bg:#555555 fg:#ffffff bold',
    'ugb.gfx.pixel.3': 'bg:#000000 fg:#aaaaaa bold',
    'ugb.sidebar.title': 'bold',
    'ugb.hl ugb.sidebar.title': 'bg:white',
    # Highlight
    'ugb.hl': 'fg:black',
    'ugb.hl ugb.data': 'bg:#55cccc',
    'ugb.hl ugb.data.empty': 'bg:#888888',
    'ugb.hl ugb.address': 'bg:#10b020',
    'ugb.hl ugb.address.data': 'bg:#10a080',
    'ugb.hl ugb.bin': 'bg:#aaaaaa',
    # Sections
    'ugb.section': 'fg:#aa0000 bold',
    # Labels
    'ugb.label.global': 'fg:ansibrightcyan bold',
    'ugb.label.local': 'fg:ansibrightyellow bold',
    # Value colors
    'ugb.value': 'fg:#ebcb4d',
    'ugb.value.reg': 'fg:ansibrightblue',
    'ugb.value.addr': 'fg:#ff99af',
    'ugb.value.cond': 'fg:ansicyan',
    'ugb.value.label': 'fg:ansibrightcyan',
    'ugb.value.special': 'fg:#e88700',
    # Instruction operation colors
    'ugb.instr.op': 'fg:ansiyellow',
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

for _op, _type in product(['call', 'jp', 'jr'], ['addr', 'label']):
    UGB_STYLE[f'ugb.value.{_type}.{_op}'] = UGB_STYLE[f'ugb.instr.op.{_op}']


class DisassemblyEditor:

    def __init__(self, asm: Disassembler):
        self.disassembler = asm
        self.prompt_active = False

        self.xrefs = XRefBrowserState()
        self.gfx = GraphicsDisplayState()

        self.filters = UGBFilters(self)
        self.prompt = UGBPrompt(self)
        self.layout = UGBLayout(self)

        self.app = Application(
            layout=self.layout.layout,
            style=Style.from_dict(UGB_STYLE),
            key_bindings=create_global_bindings(self),
            full_screen=True,
        )

    def run(self):
        main_offset = Address.from_rom_offset(0x0100)
        self.layout.main_control.seek(main_offset)
        self.app.run()


def run():
    import sys
    from ..project_save import load_project

    asm = Disassembler()

    if len(sys.argv) == 3 and sys.argv[1] == '-p':
        asm.project_name = sys.argv[2]
        load_project(asm)
    elif len(sys.argv) == 2:
        with open(sys.argv[1], 'rb') as rom_file:
            asm.load_rom(rom_file)

    DisassemblyEditor(asm).run()
