from typing import Callable, Optional

from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.layout.controls import UIContent, UIControl

from .buffer import AsmBuffer
from .render import render_data
from ..disassembler import Disassembler, ROMView


class AsmControl(UIControl):
    NO_ROM = UIContent(
        lambda _: [('', "No ROM loaded")],
        line_count=1,
        show_cursor=False,
    )

    def __init__(self, asm: Optional[Disassembler] = None):
        self.buffer = None if asm is None else AsmBuffer(ROMView(asm))
        self.scroll_offset = 0
        self.cursor_offset = 0

    def is_focusable(self) -> bool:
        return True

    def create_content(self, width: int, height: int) -> "UIContent":
        if self.buffer is None:
            return self.NO_ROM

        if self.buffer.height != height:
            self.buffer.height = height
            self.buffer.refresh()

        lines = []
        for element in self.buffer.window():
            lines.extend(render_data(element))

        return UIContent(
            lines.__getitem__,
            line_count=len(lines),
            show_cursor=False,
        )

    def get_key_bindings(self):
        return control_kbs


def rom_control_event(func: Callable[[AsmBuffer], None]):

    def handler(event: KeyPressEvent) -> None:
        control = event.app.layout.current_control
        if isinstance(control, AsmControl):
            buffer = control.buffer
            if buffer is not None:
                func(buffer)

    return handler


control_kbs = KeyBindings()


@control_kbs.add("up")
@rom_control_event
def handle_up(buffer: AsmBuffer):
    buffer.move_up(1)


@control_kbs.add("down")
@rom_control_event
def handle_down(buffer: AsmBuffer):
    buffer.move_down(1)


@control_kbs.add("pageup")
@rom_control_event
def handle_page_up(buffer: AsmBuffer):
    buffer.move_up(buffer.height)


@control_kbs.add("pagedown")
@rom_control_event
def handle_page_down(buffer: AsmBuffer):
    buffer.move_down(buffer.height)
