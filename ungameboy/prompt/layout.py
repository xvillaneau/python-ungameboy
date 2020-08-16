from typing import TYPE_CHECKING

from prompt_toolkit.layout import HSplit, Layout, Window

from .control import AsmControl

if TYPE_CHECKING:
    from .application import DisassemblyEditor


class UGBLayout:
    def __init__(self, editor: "DisassemblyEditor"):
        self.main_control = AsmControl(editor.disassembler)
        self.last_control = self.main_control

        main_window = Window(content=self.main_control)
        # noinspection PyTypeChecker
        body = HSplit([
            main_window,
            editor.prompt.container,
        ])

        self.layout = Layout(body, focused_element=main_window)

    def refresh(self):
        self.main_control.refresh()
