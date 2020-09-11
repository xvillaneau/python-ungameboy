from typing import TYPE_CHECKING, Optional

from prompt_toolkit.layout.controls import UIControl, UIContent
from prompt_toolkit.data_structures import Point

from ..address import Address
from ..dis.binary_data import BinaryData, RLEDataBlock
from ..dis.graphics import read_2bpp_values

if TYPE_CHECKING:
    from .application import DisassemblyEditor


class GraphicsDisplay:
    def __init__(self, app: 'DisassemblyEditor'):
        self.asm = app.disassembler
        self.address: Optional[Address] = None

        self.gfx_control = GraphicsControl(self)


class GraphicsControl(UIControl):
    def __init__(self, gfx: GraphicsDisplay):
        self.gfx = gfx
        self.scroll_pos = 0

        self._loaded_data: Optional[BinaryData] = None
        self._bitmap = b''

    @property
    def bitmap(self) -> bytes:
        if self.gfx.address is None:
            return b''
        latest_data = self.gfx.asm.data.get_data(self.gfx.address)
        if latest_data is not self._loaded_data:
            self._loaded_data = latest_data
            self._bitmap = self.read_bitmap()
        return self._bitmap

    def read_bitmap(self):
        if self._loaded_data is None:
            return b''
        elif isinstance(self._loaded_data, RLEDataBlock):
            bitmap = self._loaded_data.unpacked_data
        else:
            bitmap = self._loaded_data.bytes
        return bytes(read_2bpp_values(bitmap))

    def reset(self) -> None:
        self._loaded_data = None
        self._bitmap = b''

    def preferred_width(self, max_available_width: int) -> Optional[int]:
        return 16

    def is_focusable(self) -> bool:
        return True

    def create_content(self, width: int, height: int) -> "UIContent":
        bitmap = self.bitmap
        classes = [f'class:ugb.gfx.pixel.{i}' for i in range(4)]
        n_lines = ((len(bitmap) - 1) // 8) + 1

        def get_line(line: int):
            i = line * 8
            return [(classes[px], '  ') for px in bitmap[i:i + 8]]

        return UIContent(
            get_line=get_line,
            line_count=n_lines,
            cursor_position=Point(0, self.scroll_pos),
            show_cursor=False,
        )
