from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import merge_key_bindings
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.containers import ConditionalContainer, HSplit
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets.base import TextArea

from .control import AsmControl
from .key_bindings import load_buffer_bindings, load_layout_bindings
from ..commands import eval_and_run
from ..disassembler import Disassembler


class DisassemblyEditor:

    def __init__(self, asm: Disassembler):
        self.disassembler = asm
        self.prompt_active = False

        self.editor_layout = EditorLayout(self)

        ugb_style = Style.from_dict({
            'ugb.address': 'fg:green',
            'ugb.bin': 'fg:orange',
        })

        self.app = Application(
            layout=self.editor_layout.layout,
            style=ugb_style,
            key_bindings=merge_key_bindings([
                load_layout_bindings(self),
                load_buffer_bindings(self),
            ]),
            full_screen=True,
        )

    def run(self):
        self.app.run()


class EditorLayout:
    def __init__(self, editor: DisassemblyEditor):
        self.main_control = AsmControl(editor.disassembler)

        def run_cmd(buffer: Buffer):
            command = buffer.text
            if command:
                eval_and_run(editor.disassembler, command)
                self.main_control.buffer.refresh()
            else:
                editor.prompt_active = False
                editor.app.layout.focus_last()
            return False

        self.prompt = TextArea(
            prompt="> ",
            dont_extend_height=True,
            multiline=False,
            accept_handler=run_cmd,
        )

        main_window = Window(content=self.main_control)
        # noinspection PyTypeChecker
        body = HSplit([
            main_window,
            ConditionalContainer(
                self.prompt,
                Condition(lambda: editor.prompt_active)
            )
        ])

        self.layout = Layout(body, focused_element=main_window)


def run():
    import sys
    asm = Disassembler()

    if len(sys.argv) > 1:
        with open(sys.argv[1], 'rb') as rom_file:
            asm.load_rom(rom_file)

    DisassemblyEditor(asm).run()
