from typing import TYPE_CHECKING

from prompt_toolkit.layout import D, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.containers import ConditionalContainer

from .control import AsmControl

if TYPE_CHECKING:
    from .application import DisassemblyEditor


def build_xrefs_sidebar(app: 'DisassemblyEditor'):

    bar_stack = HSplit([
        Window(app.xrefs.head_control, height=1),
        Window(height=1, char='\u2500'),
        Window(app.xrefs.refs_control),
    ])

    return ConditionalContainer(
        content=VSplit([Window(width=1, char='\u2502'), bar_stack]),
        filter=app.filters.xrefs_visible,
    )


class UGBLayout:
    def __init__(self, editor: "DisassemblyEditor"):
        self.editor = editor
        self.main_control = AsmControl(editor.disassembler)

        main_window = Window(
            content=self.main_control,
            allow_scroll_beyond_bottom=True,
            get_vertical_scroll=self.main_control.get_vertical_scroll,
            width=D(weight=5),
        )
        xref_sidebar = build_xrefs_sidebar(self.editor)

        # noinspection PyTypeChecker
        body = HSplit([
            VSplit([main_window, xref_sidebar]),
            editor.prompt.container,
        ])

        self.layout = Layout(body, focused_element=main_window)

    def refresh(self):
        self.main_control.refresh()

    def focus_prompt(self):
        self.editor.prompt_active = True
        self.layout.focus(self.editor.prompt.container)

    def exit_prompt(self):
        if self.editor.prompt_active:
            self.editor.prompt_active = False
            self.layout.focus_last()
