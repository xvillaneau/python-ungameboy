import shlex
from typing import TYPE_CHECKING

import click
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.widgets.base import TextArea

from ..address import Address
from ..commands import create_core_cli

if TYPE_CHECKING:
    from .application import DisassemblyEditor


def create_ui_cli(ugb_app: "DisassemblyEditor"):
    """Add the the main CLI the UI-specific options"""
    ugb_core_cli = create_core_cli(ugb_app.disassembler)

    @ugb_core_cli.command()
    @click.argument("address", type=Address.parse)
    def seek(address: Address):
        ugb_app.layout.last_control.buffer.seek(address)
        return False

    return ugb_core_cli


class UGBPrompt:
    def __init__(self, editor: "DisassemblyEditor"):
        self.editor = editor
        self.cli = create_ui_cli(editor)

        self.prompt = TextArea(
            prompt="> ",
            dont_extend_height=True,
            multiline=False,
            accept_handler=self.accept_handler,
        )

        # noinspection PyTypeChecker
        self.container = ConditionalContainer(
            self.prompt,
            Condition(lambda: editor.prompt_active)
        )

    def accept_handler(self, buffer: Buffer):
        command = buffer.text
        if not command:
            self.editor.prompt_active = False
            self.editor.app.layout.focus_last()
            return False

        args = shlex.split(command)
        res = self.cli.main(args, "ungameboy", standalone_mode=False)
        if res is not False:
            self.editor.layout.refresh()

        return False

    def reset(self) -> None:
        self.prompt.buffer.reset()
