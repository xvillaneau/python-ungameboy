import re
import shlex
from typing import TYPE_CHECKING, Iterable

import click
from prompt_toolkit.application import get_app
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.completion import (
    Completer, CompleteEvent, Completion, NestedCompleter
)
from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.widgets.base import TextArea

from .control import AsmControl
from ..address import Address
from ..commands import AddressOrLabel, LabelName, create_core_cli

if TYPE_CHECKING:
    from .application import DisassemblyEditor
    from ..dis import Disassembler


def create_ui_cli(ugb_app: "DisassemblyEditor"):
    """Add the the main CLI the UI-specific options"""
    ugb_core_cli = create_core_cli(ugb_app.disassembler)
    address_arg = AddressOrLabel(ugb_app.disassembler)

    @ugb_core_cli.command()
    @click.argument("address", type=address_arg)
    def seek(address: Address):
        control = ugb_app.layout.layout.previous_control
        if isinstance(control, AsmControl):
            control.seek(address)
        return False

    @ugb_core_cli.command()
    @click.argument("address", type=address_arg)
    def inspect(address: Address):
        ugb_app.xrefs.address = address
        ugb_app.xrefs.index = 0
        ugb_app.prompt_active = False
        ugb_app.layout.layout.focus(ugb_app.xrefs.refs_control)
        return False

    return ugb_core_cli


class LabelCompleter(Completer):
    RE_LABEL = re.compile(r'([a-zA-Z0-9_]+(\.[a-zA-Z0-9_-]+)?)')

    def __init__(self, disassembler: "Disassembler"):
        self.asm = disassembler

    def get_completions(
            self, document: "Document", complete_event: CompleteEvent
    ) -> Iterable[Completion]:
        name_head = document.get_word_before_cursor(pattern=self.RE_LABEL)

        if not name_head:
            control = get_app().layout.previous_control
            if not isinstance(control, AsmControl):
                return

            addr = control.cursor
            dest = control.cursor_destination
            yield from (
                Completion(lb.name)
                for lb in self.asm.labels.get_labels(addr)
            )
            if dest is not None:
                yield from (
                    Completion(lb.name)
                    for lb in self.asm.labels.get_labels(dest)
                )
            yield Completion(str(addr))
            if dest is not None:
                yield Completion(str(dest))
            return

        for name in self.asm.labels.search(name_head):
            yield Completion(name, -len(name_head))


class UGBPrompt:
    def __init__(self, editor: "DisassemblyEditor"):
        self.editor = editor
        self.cli = create_ui_cli(editor)

        self.prompt = TextArea(
            prompt="> ",
            dont_extend_height=True,
            multiline=False,
            completer=self.create_completer(),
            accept_handler=self.accept_handler,
        )

        # noinspection PyTypeChecker
        self.container = ConditionalContainer(
            self.prompt,
            Condition(lambda: editor.prompt_active)
        )

    def create_completer(self):
        label_complete = LabelCompleter(self.editor.disassembler)

        def _create_cmd_completer(cmd: click.Command):
            if cmd.params:
                p0 = cmd.params[0].type
                if isinstance(p0, (AddressOrLabel, LabelName)):
                    return label_complete
            return None

        def _iter_click_groups(group):
            opts = {}
            for name in group.list_commands(None):
                cmd = group.get_command(None, name)
                if isinstance(cmd, click.MultiCommand):
                    value = _iter_click_groups(cmd)
                elif isinstance(cmd, click.Command):
                    value = _create_cmd_completer(cmd)
                else:
                    value = None
                opts[name] = value
            return opts

        cli_dict = _iter_click_groups(self.cli)
        return NestedCompleter.from_nested_dict(cli_dict)

    def accept_handler(self, buffer: Buffer):
        if buffer.text:
            self.run_command(*shlex.split(buffer.text))

        self.editor.layout.exit_prompt()
        return False

    def pre_fill(self, *args: str):
        line = ' '.join(shlex.quote(arg) for arg in args) + ' '
        self.prompt.buffer.reset(Document(line))

    def run_command(self, *args):
        res = self.cli.main(args, "ungameboy", standalone_mode=False)
        if res is not False:
            self.editor.layout.refresh()
        return res

    def reset(self) -> None:
        self.prompt.buffer.reset()
