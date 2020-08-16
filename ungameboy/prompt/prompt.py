from typing import TYPE_CHECKING

from prompt_toolkit.buffer import Buffer
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout.containers import ConditionalContainer
from prompt_toolkit.widgets.base import TextArea

from ..address import Address
from ..commands import eval_and_run

if TYPE_CHECKING:
    from .application import DisassemblyEditor


class UGBPrompt:
    def __init__(self, editor: "DisassemblyEditor"):
        self.editor = editor

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

        prefix, *_ = command.split(maxsplit=1)
        if prefix in UI_COMMANDS:
            _, addr = command.split()
            UI_COMMANDS[prefix](self.editor, Address.parse(addr))
        else:
            eval_and_run(self.editor.disassembler, command)
            self.editor.layout.refresh()

        return False

    def reset(self) -> None:
        self.prompt.buffer.reset()


UI_COMMANDS = {}


def register(name: str):
    def decorator(func):
        UI_COMMANDS[name] = func
        return func
    return decorator


@register("seek")
def _seek_to(ugb_app: "DisassemblyEditor", address: Address):
    ugb_app.layout.last_control.buffer.seek(address)
