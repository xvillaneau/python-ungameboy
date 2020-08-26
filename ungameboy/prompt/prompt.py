import re
import shlex
from typing import TYPE_CHECKING, Iterable

import click
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import (
    Completer, CompleteEvent, Completion, NestedCompleter
)
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.widgets.base import TextArea

from ..address import Address
from ..commands import AddressOrLabel, LabelName, create_core_cli

if TYPE_CHECKING:
    from prompt_toolkit.document import Document
    from .application import DisassemblyEditor
    from ..disassembler import Disassembler


def create_ui_cli(ugb_app: "DisassemblyEditor"):
    """Add the the main CLI the UI-specific options"""
    ugb_core_cli = create_core_cli(ugb_app.disassembler)

    @ugb_core_cli.command()
    @click.argument("address", type=Address.parse)
    def seek(address: Address):
        ugb_app.layout.main_control.seek(address)
        return False

    return ugb_core_cli


class LabelCompleter(Completer):
    RE_LABEL = re.compile(r'([a-zA-Z0-9_]+(\.[a-zA-Z0-9_]+)?)')

    def __init__(self, asm: "Disassembler"):
        self.asm = asm

    def get_completions(
            self, document: "Document", complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        name_head = document.get_word_before_cursor(pattern=self.RE_LABEL)
        for name in self.asm.labels.search(name_head):
            yield Completion(name, -len(name_head))


def create_cmd_completer(cmd: click.Command):
    if cmd.params:
        p0 = cmd.params[0].type
        if isinstance(p0, (AddressOrLabel, LabelName)):
            return LabelCompleter(p0.asm)
    return None


def create_ui_completer(cli: click.MultiCommand):

    def _iter_click_groups(group):
        opts = {}
        for name in group.list_commands(None):
            cmd = group.get_command(None, name)
            if isinstance(cmd, click.MultiCommand):
                value = _iter_click_groups(cmd)
            elif isinstance(cmd, click.Command):
                value = create_cmd_completer(cmd)
            else:
                value = None
            opts[name] = value
        return opts

    cli_dict = _iter_click_groups(cli)
    return NestedCompleter.from_nested_dict(cli_dict)


class UGBPrompt:
    def __init__(self, editor: "DisassemblyEditor"):
        self.editor = editor
        self.cli = create_ui_cli(editor)

        self.prompt = TextArea(
            prompt="> ",
            dont_extend_height=True,
            multiline=False,
            completer=create_ui_completer(self.cli),
            accept_handler=self.accept_handler,
        )

        # noinspection PyTypeChecker
        self.container = ConditionalContainer(
            self.prompt,
            Condition(lambda: editor.prompt_active)
        )

    def accept_handler(self, buffer: Buffer):
        if buffer.text:
            args = shlex.split(buffer.text)
            res = self.cli.main(args, "ungameboy", standalone_mode=False)
            if res is not False:
                self.editor.layout.refresh()

        self.editor.prompt_active = False
        self.editor.app.layout.focus_last()
        return False

    def reset(self) -> None:
        self.prompt.buffer.reset()
