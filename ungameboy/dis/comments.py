import re
from typing import TYPE_CHECKING, List

import click

from .manager_base import AsmManager
from ..address import Address
from ..commands import AddressOrLabel
from ..data_structures import AddressMapping

if TYPE_CHECKING:
    from .disassembler import Disassembler


class CommentsManager(AsmManager):
    def __init__(self, asm: 'Disassembler'):
        super().__init__(asm)
        self.inline: AddressMapping[str] = AddressMapping()
        self.block: AddressMapping[List[str]] = AddressMapping()

    def reset(self) -> None:
        self.inline.clear()
        self.block.clear()

    def build_cli(self) -> 'click.Command':
        comments_cli = click.Group('comment')
        address_arg = AddressOrLabel(self.asm)

        @comments_cli.command()
        @click.argument('address', type=address_arg)
        def clear(address):
            if address in self.inline:
                del self.inline[address]
            if address in self.block:
                del self.block[address]

        @comments_cli.command()
        @click.argument('address', type=address_arg)
        @click.argument('comment', required=True, nargs=-1)
        def inline(address, comment):
            full_comment = ' '.join(comment)
            self.inline[address] = full_comment

        return comments_cli

    def save_items(self):
        for addr, comment in self.inline.items():
            yield ('comment', 'inline', addr, comment)

    def set_inline(self, address: Address, comment: str):
        # Get rid of any exotic whitespace or line break
        comment = re.sub(r'\s', ' ', comment).rstrip()
        if comment:
            self.inline[address] = comment
        elif address in self.inline:
            del self.inline[address]
