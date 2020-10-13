from functools import partial
from itertools import product

from prompt_toolkit.application import Application
from prompt_toolkit.eventloop import run_in_executor_with_context
from prompt_toolkit.layout.containers import Float, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets.dialogs import Dialog

from .filters import UGBFilters
from .gfx_display import GraphicsDisplayState
from .key_bindings import create_global_bindings
from .layout import UGBLayout
from .prompt import UGBPrompt
from .xref_browser import XRefBrowserState
from ..address import Address
from ..dis import Disassembler


UGB_STYLE = {
    'ugb.bin': 'fg:#aaaaaa',
    'ugb.comment': 'fg:#bbbbbb',
    'ugb.data': 'fg:#55cccc',
    'ugb.data.empty': 'fg:#888888',
    'ugb.data.key': 'fg:#cc6666',
    'ugb.data.value': 'fg:#ebcb4d',
    'ugb.flags': 'fg:#aaaa55',
    'ugb.xrefs': 'fg:#cc5555',
    # Graphics
    'ugb.gfx.pixel.0': 'bg:#ffffff fg:#555555 bold',
    'ugb.gfx.pixel.1': 'bg:#aaaaaa fg:#000000 bold',
    'ugb.gfx.pixel.2': 'bg:#555555 fg:#ffffff bold',
    'ugb.gfx.pixel.3': 'bg:#000000 fg:#aaaaaa bold',
    'ugb.sidebar.title': 'bold',
    # Address classes
    'ugb.address': 'fg:#10b020',
    'ugb.address ugb.data': 'fg:#10a080',
    'ugb.address ugb.data.empty': 'fg:#888888',
    # Highlight
    'ugb.hl': 'fg:black',
    'ugb.hl ugb.data': 'bg:#55cccc',
    'ugb.hl ugb.data.empty': 'bg:#888888',
    'ugb.hl ugb.address': 'bg:#10b020',
    'ugb.hl ugb.address.data': 'bg:#10a080',
    'ugb.hl ugb.address.data.empty': 'bg:#888888',
    'ugb.hl ugb.bin': 'bg:#aaaaaa',
    'ugb.hl ugb.comment': 'bg:#bbbbbb',
    'ugb.hl ugb.sidebar.title': 'bg:white',
    # Sections
    'ugb.section': 'fg:#aa0000 bold',
    # Labels
    'ugb.label.global': 'fg:ansibrightcyan bold',
    'ugb.label.local': 'fg:ansibrightyellow bold',
    # Value colors
    'ugb.value': 'fg:#ebcb4d',
    'ugb.value.reg': 'fg:ansibrightblue',
    'ugb.value.addr': 'fg:#ff99af',
    'ugb.value.cond': 'fg:ansicyan',
    'ugb.value.label': 'fg:ansibrightcyan',
    'ugb.value.special': 'fg:#e88700',
    # Instruction operation colors
    'ugb.instr.op': 'fg:ansiyellow',
    'ugb.instr.op.nop': 'fg:ansiblue',
    'ugb.instr.op.ret': 'fg:ansired bold',
    'ugb.instr.op.reti': 'fg:ansired bold',
    'ugb.instr.op.call': 'fg:ansibrightgreen bold',
    'ugb.instr.op.rst': 'fg:ansibrightgreen bold',
    'ugb.instr.op.jp': 'fg:ansigreen bold',
    'ugb.instr.op.jr': 'fg:ansigreen bold',
    'ugb.instr.op.ld': 'fg:ansibrightmagenta',
    'ugb.instr.op.ldh': 'fg:ansibrightmagenta',
    'ugb.instr.op.ldi': 'fg:ansibrightmagenta',
    'ugb.instr.op.ldd': 'fg:ansibrightmagenta',
    'ugb.instr.op.pop': 'fg:ansibrightcyan bold',
    'ugb.instr.op.push': 'fg:ansibrightcyan bold',
    'ugb.instr.op.invalid': 'fg:ansired',
}

for _op, _type in product(['call', 'jp', 'jr'], ['addr', 'label']):
    UGB_STYLE[f'ugb.value.{_type}.{_op}'] = UGB_STYLE[f'ugb.instr.op.{_op}']


class UGBApplication:

    def __init__(self, asm: Disassembler):
        self.asm = asm
        self.prompt_active = False

        self.xrefs = XRefBrowserState()
        self.gfx = GraphicsDisplayState()

        self.filters = UGBFilters(self)
        self.prompt = UGBPrompt(self)
        self.layout = UGBLayout(self)

        self.app = Application(
            layout=self.layout.layout,
            style=Style.from_dict(UGB_STYLE),
            key_bindings=create_global_bindings(self),
            full_screen=True,
        )

    def run(self):
        def _pre_run():
            self.app.create_background_task(self._pre_run())

        main_offset = Address.from_rom_offset(0x0100)
        self.layout.main_control.seek(main_offset)
        self.app.run(pre_run=_pre_run)

    async def _pre_run(self):
        """Run the initialization tasks asynchronously"""

        # Prepare the loading progress dialog
        progress_msg = "Loading project"
        progress_ctrl = Window(FormattedTextControl(
            text=lambda: progress_msg, focusable=True, show_cursor=False
        ))
        # noinspection PyTypeChecker
        progress_float = Float(Dialog(progress_ctrl, "Loading…"))

        self.layout.floats.append(progress_float)
        self.app.layout.focus(progress_ctrl)
        self.app.invalidate()

        # Loading the project is a blocking task, therefore it needs
        # to be run in a separate thread.
        def _load():
            self.asm.auto_load()
            self.layout.refresh()

        try:
            await run_in_executor_with_context(_load)

            if not self.asm.is_loaded:
                return

            # Seek to the ROM start offset
            main_offset = Address.from_rom_offset(0x0100)
            self.layout.main_control.seek(main_offset)
            self.app.invalidate()

            # Index all the banks. This can take a while.
            n_banks = self.asm.rom.n_banks
            for bank in range(n_banks):
                progress_msg = f"Indexing bank {bank:02x}/{n_banks-1:02x}"
                index = partial(self.asm.xrefs.index, bank)
                await run_in_executor_with_context(index)
                self.app.invalidate()

        finally:
            self.app.layout.focus_last()
            self.layout.floats.remove(progress_float)

        self.layout.refresh()
        self.app.invalidate()


def run():
    import sys

    asm = Disassembler()

    if len(sys.argv) == 3 and sys.argv[1] == '-p':
        asm.project_name = sys.argv[2]
    elif len(sys.argv) == 2:
        asm.rom_path = sys.argv[1]

    UGBApplication(asm).run()
