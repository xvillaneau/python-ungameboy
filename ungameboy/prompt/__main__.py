from typing import Optional

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.styles import Style

from ungameboy.address import Address, ROM0
from ungameboy.data_block import DataBlock
from ungameboy.decoder import ROMBytes
from ungameboy.disassembler import Disassembler
from ungameboy.prompt.control import AsmControl


class DisassemblyEditor:
    opened_rom: Optional[ROMBytes] = None
    running_command = None

    def __init__(self, asm=None):
        self.control = AsmControl(asm)

        ugb_style = Style.from_dict({
            'ugb.address': 'fg:green',
            'ugb.bin': 'fg:orange',
        })

        self.window = Window(content=self.control)

        self.app = Application(
            layout=Layout(
                HSplit([self.window]),
                focused_element=self.window,
            ),
            style=ugb_style,
            key_bindings=global_kb,
            full_screen=True,
        )

    def run(self):
        self.app.run()


global_kb = KeyBindings()


@global_kb.add("c-d")
def _exit(event):
    event.app.exit()


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1:
        _asm = Disassembler(ROMBytes.from_path(sys.argv[1]))
        _asm.data.insert(DataBlock(Address(ROM0, 0x104), 0x30, "Nintendo logo"))
        _asm.data.insert(DataBlock(Address(ROM0, 0x134), 0x1c, "Cartridge header"))
    else:
        _asm = None
    DisassemblyEditor(_asm).run()
