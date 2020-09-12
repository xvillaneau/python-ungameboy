from functools import reduce
from operator import or_
from typing import TYPE_CHECKING

from prompt_toolkit.layout import D, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.containers import ConditionalContainer

from .control import AsmControl
from .gfx_display import GraphicsControl

if TYPE_CHECKING:
    from .application import DisassemblyEditor


class UGBLayout:
    def __init__(self, app: "DisassemblyEditor"):
        self.app = app
        self.main_control = AsmControl(app.disassembler)
        self.gfx_control = GraphicsControl(app)

        main_window = Window(
            content=self.main_control,
            allow_scroll_beyond_bottom=True,
            get_vertical_scroll=self.main_control.get_vertical_scroll,
            width=D(weight=5),
        )

        # noinspection PyTypeChecker
        body = HSplit([
            VSplit([main_window, self.build_sidebar()]),
            app.prompt.container,
        ])

        self.layout = Layout(body, focused_element=main_window)

    def build_sidebar(self):
        xrefs_view = HSplit([
            Window(self.app.xrefs.head_control, height=1),
            Window(height=1, char='\u2500'),
            Window(self.app.xrefs.refs_control),
        ])
        gfx_window = Window(
            content=self.gfx_control,
            get_vertical_scroll=lambda _: self.gfx_control.scroll_pos,
            allow_scroll_beyond_bottom=True,
        )

        views = [
            (xrefs_view, self.app.filters.xrefs_visible),
            (gfx_window, self.app.filters.gfx_visible),
        ]

        separator = ConditionalContainer(
            content=Window(width=1, char='\u2502'),
            filter=reduce(or_, (filter for _, filter in views))
        )
        stack = HSplit([
            ConditionalContainer(content=view, filter=filter)
            for view, filter in views
        ])

        return VSplit([separator, stack])

    def refresh(self):
        self.main_control.refresh()

    def focus_prompt(self):
        self.app.prompt_active = True
        self.layout.focus(self.app.prompt.container)

    def exit_prompt(self):
        if self.app.prompt_active:
            self.app.prompt_active = False
            self.layout.focus_last()
