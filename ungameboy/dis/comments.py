from base64 import b64decode, b64encode
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
        self.blocks: AddressMapping[List[str]] = AddressMapping()

    def reset(self) -> None:
        self.inline.clear()
        self.blocks.clear()

    def clear(self, address: Address):
        if address in self.inline:
            del self.inline[address]
        if address in self.blocks:
            del self.blocks[address]

    def set_inline(self, address: Address, comment: str):
        # Get rid of any exotic whitespace or line break
        comment = re.sub(r'\s', ' ', comment).rstrip()
        if comment:
            self.inline[address] = comment
        elif address in self.inline:
            del self.inline[address]

    def set_block_line(self, address: Address, index: int, comment: str):
        if index < 0:
            return
        comment = re.sub(r'\s', ' ', comment)
        block = self.blocks.setdefault(address, [])
        if index >= len(block):
            block.extend([''] * (index - len(block) + 1))
        block[index] = comment

    def append_block_line(self, address: Address, comment: str):
        self.add_block_line(address, -1, comment)

    def add_block_line(self, address: Address, index: int, comment: str):
        comment = re.sub(r'\s', ' ', comment).rstrip()
        block = self.blocks.setdefault(address, [])
        if not 0 <= index <= len(block):
            index = len(block)
        block.insert(index, comment)

    def pop_block_line(self, address: Address, index: int):
        if address not in self.blocks:
            return
        block = self.blocks.get(address)
        if not 0 <= index < len(block):
            index = len(block) - 1
        if block:  # In case an empty block exists
            block.pop(index)
        if not block:  # Remove empty blocks
            del self.blocks[address]

    def build_cli(self) -> 'click.Command':
        comments_cli = click.Group('comment')
        address_arg = AddressOrLabel(self.asm)

        def process_comment(comment, b64=False):
            if b64:
                if len(comment) != 1:
                    raise ValueError()
                return b64decode(comment[0]).decode("utf-8")
            else:
                return ' '.join(comment)

        @comments_cli.command()
        @click.argument('address', type=address_arg)
        def clear(address):
            self.clear(address)

        @comments_cli.command()
        @click.argument('address', type=address_arg)
        @click.argument('comment', required=True, nargs=-1)
        @click.option('--b64', is_flag=True)
        def inline(address, comment, b64=False):
            self.set_inline(address, process_comment(comment, b64))

        @comments_cli.command()
        @click.argument('address', type=address_arg)
        @click.argument('comment', required=True, nargs=-1)
        @click.option('--b64', is_flag=True)
        def append(address, comment, b64=False):
            self.append_block_line(address, process_comment(comment, b64))

        return comments_cli

    def save_items(self):
        def encode(comm):
            return b64encode(comm.encode("utf8")).decode("ascii")

        for addr, comment in self.inline.items():
            yield ('comment', 'inline', addr, encode(comment), "--b64")
        for addr, lines in self.blocks.items():
            for comment in lines:
                yield ('comment', 'append', addr, encode(comment), "--b64")
