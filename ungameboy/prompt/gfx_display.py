from typing import TYPE_CHECKING, Optional

from prompt_toolkit.layout.controls import FormattedTextControl

from .key_bindings import create_gfx_display_bindings
from ..address import Address
from ..dis.graphics import read_2bpp_values

if TYPE_CHECKING:
    from .application import DisassemblyEditor


class GraphicsDisplay:
    def __init__(self, app: 'DisassemblyEditor'):
        self.asm = app.disassembler
        self.address: Optional[Address] = None

        self.gfx_control = FormattedTextControl(
            self.get_content,
            focusable=True,
            show_cursor=False,
            key_bindings=create_gfx_display_bindings(app),
        )

    def get_content(self):
        if self.address is None:
            return []

        data = self.asm.data.get_data(self.address)
        if data is None:
            return [('', 'No data found at that address')]

        classes = [f'class:ugb.gfx.pixel.{i}' for i in range(4)]

        tokens = []
        pixels = read_2bpp_values(data.bytes)
        for i, pixel in enumerate(pixels, start=1):
            tokens.append((classes[pixel], '  '))
            if i % 8 == 0:
                tokens.append(('', '\n'))

        return tokens
