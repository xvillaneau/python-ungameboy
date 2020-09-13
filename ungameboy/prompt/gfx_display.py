from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from prompt_toolkit.layout.containers import Window
from prompt_toolkit.layout.controls import UIControl, UIContent
from prompt_toolkit.data_structures import Point

from .key_bindings import create_gfx_display_bindings
from ..address import Address
from ..dis.binary_data import BinaryData, RLEDataBlock
from ..dis.graphics import read_2bpp_values

if TYPE_CHECKING:
    from .application import DisassemblyEditor


@dataclass
class GraphicsDisplayState:
    address: Optional[Address] = None
    columns: int = 2
    tile_height: int = 8
    show_ids: bool = False


class GraphicsControl(UIControl):
    def __init__(self, app: 'DisassemblyEditor'):
        self.app = app
        self.gfx = app.gfx
        self.scroll_pos = 0

        self._loaded_data: Optional[BinaryData] = None
        self._bitmap = b''
        self._kb = create_gfx_display_bindings(app)

    def make_window(self):
        return Window(
            content=self,
            get_vertical_scroll=self.get_scroll_pos,
            allow_scroll_beyond_bottom=True,
        )

    def get_scroll_pos(self, _):
        return self.scroll_pos

    @property
    def bitmap(self) -> bytes:
        if self.gfx.address is None:
            return b''

        latest_data = self.app.disassembler.data.get_data(self.gfx.address)
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
        self.scroll_pos = 0
        self._loaded_data = None
        self._bitmap = b''

    def preferred_width(self, max_available_width: int) -> Optional[int]:
        return 16 * self.gfx.columns

    @property
    def height(self):
        cols, size = self.gfx.columns, self.gfx.tile_height
        return (((len(self.bitmap) - 1) // (8 * cols * size)) + 1) * size

    def get_key_bindings(self):
        return self._kb

    def is_focusable(self) -> bool:
        return True

    def create_content(self, width: int, height: int) -> "UIContent":
        bitmap = self.bitmap
        cols, size = self.gfx.columns, self.gfx.tile_height

        classes = [f'class:ugb.gfx.pixel.{i}' for i in range(4)]

        def get_line(line: int):
            i = (line % size) * 8 + (line // size) * cols * size * 8
            tokens = []
            for _ in range(cols):
                row = bitmap[i:i + 8]
                tokens.extend((classes[px], '  ') for px in row)
                if self.gfx.show_ids and i % 64 == 0 and row:
                    tile_num = f'{i // 64:04x}'
                    tokens[-8] = (tokens[-8][0], tile_num[0:2])
                    tokens[-7] = (tokens[-7][0], tile_num[2:4])
                i += size * 8
            return tokens

        return UIContent(
            get_line=get_line,
            line_count=self.height,
            cursor_position=Point(0, self.scroll_pos),
            show_cursor=False,
        )

    def move_down(self, n):
        self.scroll_pos = min(self.scroll_pos + n, self.height - 1)

    def move_up(self, n):
        self.scroll_pos = max(self.scroll_pos - n, 0)
