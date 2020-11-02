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
from ..project_save import load_project


UGB_STYLE = {
    'bin': 'fg:#aaaaaa',
    'comment': 'fg:#bbbbbb',
    'data': 'fg:#55cccc',
    'data.empty': 'fg:#888888',
    'data.key': 'fg:#cc6666',
    'data.value': 'fg:#ebcb4d',
    'flags': 'fg:#aaaa55',
    'xrefs': 'fg:#cc5555',
    # Graphics
    'gfx.pixel.0': 'bg:#ffffff fg:#555555 bold',
    'gfx.pixel.1': 'bg:#aaaaaa fg:#000000 bold',
    'gfx.pixel.2': 'bg:#555555 fg:#ffffff bold',
    'gfx.pixel.3': 'bg:#000000 fg:#aaaaaa bold',
    'sidebar.title': 'bold',
    # Address classes
    'address': 'fg:#10b020',
    'address data': 'fg:#10a080',
    'address data.empty': 'fg:#888888',
    # Highlight
    'hl': 'fg:black',
    'hl data': 'bg:#55cccc',
    'hl data.empty': 'bg:#888888',
    'hl address': 'bg:#10b020',
    'hl address.data': 'bg:#10a080',
    'hl address.data.empty': 'bg:#888888',
    'hl bin': 'bg:#aaaaaa',
    'hl comment': 'bg:#bbbbbb',
    'hl sidebar.title': 'bg:white',
    # Sections
    'section': 'fg:#aa0000 bold',
    # Labels
    'label.global': 'fg:ansibrightcyan bold',
    'label.local': 'fg:ansibrightyellow bold',
    # Value colors
    'value': 'fg:#ebcb4d',
    'value.reg': 'fg:ansibrightblue',
    'value.addr': 'fg:#ff99af',
    'value.cond': 'fg:ansicyan',
    'value.label': 'fg:ansibrightcyan',
    'value.special': 'fg:#e88700',
    # Instruction operation colors
    'instr.op': 'fg:ansiyellow',
    'instr.op.nop': 'fg:ansiblue',
    'instr.op.ret': 'fg:ansired bold',
    'instr.op.reti': 'fg:ansired bold',
    'instr.op.call': 'fg:ansibrightgreen bold',
    'instr.op.rst': 'fg:ansibrightgreen bold',
    'instr.op.jp': 'fg:ansigreen bold',
    'instr.op.jr': 'fg:ansigreen bold',
    'instr.op.ld': 'fg:ansibrightmagenta',
    'instr.op.ldh': 'fg:ansibrightmagenta',
    'instr.op.ldi': 'fg:ansibrightmagenta',
    'instr.op.ldd': 'fg:ansibrightmagenta',
    'instr.op.pop': 'fg:ansibrightcyan bold',
    'instr.op.push': 'fg:ansibrightcyan bold',
    'instr.op.invalid': 'fg:ansired',
}

for _op, _type in product(['call', 'jp', 'jr'], ['addr', 'label']):
    UGB_STYLE[f'value.{_type}.{_op}'] = UGB_STYLE[f'instr.op.{_op}']


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

    def _startup_tasks(self):
        """
        Sequence of tasks run when opening UGB. Iterator that yields
        loading progress messages and awaitable objects.
        """
        if self.asm.is_loaded:
            return

        run_rom_setup = False

        if self.asm.project_name:
            def _load_project():
                load_project(self.asm)
                self.layout.refresh()

            task = run_in_executor_with_context(_load_project)
            yield "Loading project", task

        elif self.asm.rom_path:
            def _load_rom():
                with open(self.asm.rom_path, 'rb') as rom:
                    self.asm.load_rom(rom)
                self.layout.refresh()

            task = run_in_executor_with_context(_load_rom)
            yield "Loading ROM", task
            run_rom_setup = True

        if not self.asm.is_loaded:
            return

        main_offset = Address.from_rom_offset(0x0100)
        self.layout.main_control.seek(main_offset)
        yield "", None

        if run_rom_setup:
            yield "Setting up ROM", run_in_executor_with_context(
                self.asm.setup_new_rom
            )
            yield "Detecting empty banks", run_in_executor_with_context(
                self.asm.analyze.detect_empty_banks
            )

        # Index all the banks. This can take a while.
        n_banks = self.asm.rom.n_banks
        for bank in range(n_banks):
            msg = f"Indexing bank {bank:02x}/{n_banks - 1:02x}"
            index = partial(self.asm.xrefs.index, bank, fast=True)
            yield msg, run_in_executor_with_context(index)

        yield "", run_in_executor_with_context(self.layout.refresh)

    async def _pre_run(self):
        """Run the initialization tasks asynchronously"""

        # Prepare the loading progress dialog
        progress_msg = "Starting UnGameBoy"
        progress_ctrl = Window(FormattedTextControl(
            text=lambda: progress_msg, focusable=True, show_cursor=False
        ))
        # noinspection PyTypeChecker
        progress_float = Float(Dialog(progress_ctrl, "Loading…"))

        self.layout.floats.append(progress_float)
        self.app.layout.focus(progress_ctrl)
        self.app.invalidate()

        try:
            for msg, task in self._startup_tasks():
                if msg:
                    progress_msg = msg
                if task:
                    await task
                self.app.invalidate()

        finally:
            self.app.layout.focus_last()
            self.prompt.refresh_completion()
            self.layout.floats.remove(progress_float)


def run():
    import sys

    asm = Disassembler()

    if len(sys.argv) == 3 and sys.argv[1] == '-p':
        asm.project_name = sys.argv[2]
    elif len(sys.argv) == 2:
        asm.rom_path = sys.argv[1]

    UGBApplication(asm).run()
