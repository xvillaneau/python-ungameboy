from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import merge_key_bindings
from prompt_toolkit.styles import Style

from .key_bindings import load_buffer_bindings, load_layout_bindings
from .layout import UGBLayout
from .prompt import UGBPrompt
from ..disassembler import Disassembler


class DisassemblyEditor:

    def __init__(self, asm: Disassembler):
        self.disassembler = asm
        self.prompt_active = False

        self.prompt = UGBPrompt(self)
        self.layout = UGBLayout(self)

        ugb_style = Style.from_dict({
            'ugb.address': 'fg:green',
            'ugb.bin': 'fg:orange',
        })

        self.app = Application(
            layout=self.layout.layout,
            style=ugb_style,
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
    asm = Disassembler()

    if len(sys.argv) > 1:
        with open(sys.argv[1], 'rb') as rom_file:
            asm.load_rom(rom_file)

    DisassemblyEditor(asm).run()
