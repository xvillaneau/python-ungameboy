from functools import update_wrapper
from typing import BinaryIO, TYPE_CHECKING

import click

from .address import Address

if TYPE_CHECKING:
    from .disassembler import Disassembler

__all__ = ['create_core_cli']


def pass_object(func):
    @click.pass_context
    def command(ctx, *args, **kwargs):
        return ctx.invoke(func, ctx.obj, *args, **kwargs)
    return update_wrapper(command, func)


def create_core_cli(asm: "Disassembler"):

    @click.group()
    @click.pass_context
    def ugb_core_cli(ctx: click.Context):
        ctx.obj = asm

    ugb_core_cli.add_command(load_rom)
    ugb_core_cli.add_command(data_cli)
    ugb_core_cli.add_command(label_cli)

    return ugb_core_cli


# Base commands

@click.command()
@click.argument("rom_path", type=click.File('rb'))
@pass_object
def load_rom(asm: "Disassembler", rom_path: BinaryIO):
    asm.load_rom(rom_path)


# Data commands

@click.group("data")
def data_cli():
    pass


@data_cli.command("create")
@click.argument("address", type=Address.parse)
@click.argument("size", type=int, default=1)
@click.argument("name", default='')
@pass_object
def data_create(asm: "Disassembler", address: Address, size=1, name=''):
    asm.data.create(address, size, name)


@data_cli.command("rename")
@click.argument("address", type=Address.parse)
@click.argument("name", default='')
@pass_object
def data_rename(asm: "Disassembler", address: Address, name=''):
    data = asm.data.get_data(address)
    if data is None:
        return
    data.description = name


# Label commands

@click.group("label")
def label_cli():
    pass


@label_cli.command("create")
@click.argument("address", type=Address.parse)
@click.argument("name")
@pass_object
def label_create(asm, address: Address, name: str):
    asm.labels.create(address, name)
