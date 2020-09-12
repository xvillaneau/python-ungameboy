from typing import TYPE_CHECKING, Union, Callable

from prompt_toolkit.application import get_app
from prompt_toolkit.layout import D, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl

from .control import AsmControl
from .gfx_display import GraphicsControl
from .xref_browser import make_xrefs_control, make_xrefs_title_function

if TYPE_CHECKING:
    from .application import DisassemblyEditor


class UGBLayout:
    def __init__(self, app: "DisassemblyEditor"):
        self.app = app
        self.main_control = AsmControl(app.disassembler)
        self.gfx_control = GraphicsControl(app)
        self.xrefs_control = make_xrefs_control(app)

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

        xrefs = make_sidebar_container(
            self.xrefs_control, make_xrefs_title_function(self.app)
        )
        gfx = make_sidebar_container(self.gfx_control, "Bitmap preview")

        views = [
            (xrefs, self.app.filters.xrefs_visible),
            (gfx, self.app.filters.gfx_visible),
        ]

        return HSplit([
            ConditionalContainer(content=HSplit(windows), filter=filter)
            for windows, filter in views
        ])

    def refresh(self):
        self.main_control.refresh()

    def focus_prompt(self):
        self.app.prompt_active = True
        self.layout.focus(self.app.prompt.container)

    def exit_prompt(self):
        if self.app.prompt_active:
            self.app.prompt_active = False
            self.layout.focus_last()


def make_sidebar_container(control, header: Union[str, Callable[[], str]]):

    def header_content():
        if callable(header):
            text = header()
        else:
            text = header

        format = 'class:ugb.sidebar.title'
        if get_app().layout.current_control is control:
            format += ',ugb.hl'
        return [(format, text)]

    return [
        Window(height=1),
        Window(FormattedTextControl(header_content), height=1),
        Window(height=1),
        Window(control),
    ]
