from typing import TYPE_CHECKING, Callable, List, Union

from prompt_toolkit.application import get_app
from prompt_toolkit.layout import D, HSplit, Layout, VSplit, Window
from prompt_toolkit.layout.containers import (
    ConditionalContainer, Float, FloatContainer
)
from prompt_toolkit.layout.controls import FormattedTextControl

from .control import AsmControl
from .gfx_display import GraphicsControl
from .xref_browser import make_xrefs_control, make_xrefs_title_function

if TYPE_CHECKING:
    from .application import UGBApplication


class UGBLayout:
    def __init__(self, ugb: "UGBApplication"):
        self.ugb = ugb
        self.main_control = AsmControl(ugb.asm)
        self.gfx_control = GraphicsControl(ugb)
        self.xrefs_control = make_xrefs_control(ugb)
        self.floats: List[Float] = []

        main_window = Window(
            content=self.main_control,
            allow_scroll_beyond_bottom=True,
            get_vertical_scroll=self.main_control.get_vertical_scroll,
            width=D(weight=5),
        )

        # noinspection PyTypeChecker
        body = FloatContainer(
            content=HSplit([
                VSplit([main_window, self.build_sidebar()]),
                ugb.prompt.container,
            ]),
            floats=self.floats,
        )

        self.layout = Layout(body, focused_element=main_window)

    def build_sidebar(self):

        views = [
            (
                Window(self.xrefs_control),
                make_xrefs_title_function(self.ugb),
                self.ugb.filters.xrefs_visible
            ),
            (
                self.gfx_control.make_window(),
                "Bitmap preview",
                self.ugb.filters.gfx_visible
            ),
        ]

        return HSplit([
            make_sidebar_container(window, header, filter)
            for window, header, filter in views
        ])

    def refresh(self):
        self.main_control.refresh()

    def focus_prompt(self):
        self.ugb.prompt_active = True
        self.layout.focus(self.ugb.prompt.container)

    def exit_prompt(self):
        if self.ugb.prompt_active:
            self.ugb.prompt_active = False
            self.layout.focus_last()


def make_sidebar_container(
        window, header: Union[str, Callable[[], str]], filter
):

    def header_content():
        if callable(header):
            text = header()
        else:
            text = header

        format = 'class:sidebar.title'
        if get_app().layout.current_window is window:
            format += ',hl'
        return [(format, text)]

    windows = [
        Window(height=1),
        Window(FormattedTextControl(header_content), height=1),
        Window(height=1),
        window,
    ]
    return ConditionalContainer(content=HSplit(windows), filter=filter)
