from typing import Optional

from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.styles import Style

from ungameboy.decoder import ROMBytes
from ungameboy.prompt.control import ROMControl


class DisassemblyEditor:
    opened_rom: Optional[ROMBytes] = None
    running_command = None

    def __init__(self, rom=None):
        self.control = ROMControl(rom)

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
        _rom = ROMBytes.from_path(sys.argv[1])
    else:
        _rom = None
    DisassemblyEditor(_rom).run()
