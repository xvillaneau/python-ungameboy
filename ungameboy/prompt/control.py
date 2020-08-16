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

    def __init__(self, asm: Disassembler):
        self.asm = asm
        self.buffer = AsmBuffer(ROMView(asm))

    def refresh(self) -> None:
        self.buffer.refresh()

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
