from typing import TYPE_CHECKING

from prompt_toolkit.layout import HSplit, Layout, Window

from .control import AsmControl

if TYPE_CHECKING:
    from .application import DisassemblyEditor


class UGBLayout:
    def __init__(self, editor: "DisassemblyEditor"):
        self.editor = editor
        self.main_control = AsmControl(editor.disassembler)

        main_window = Window(
            content=self.main_control,
            allow_scroll_beyond_bottom=True,
            get_vertical_scroll=self.main_control.get_vertical_scroll,
        )
        # noinspection PyTypeChecker
        body = HSplit([
            main_window,
            editor.prompt.container,
        ])

        self.layout = Layout(body, focused_element=main_window)

    def refresh(self):
        self.main_control.refresh()

    def focus_prompt(self):
        self.editor.prompt_active = True
        self.layout.focus(self.editor.prompt.container)

    def unfocus_prompt(self):
        self.editor.prompt_active = False
        self.layout.focus_last()
