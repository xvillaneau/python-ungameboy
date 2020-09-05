from typing import TYPE_CHECKING, BinaryIO

import click

from .address import Address
from .project_save import save_project, load_project

if TYPE_CHECKING:
    from .dis.disassembler import Disassembler

__all__ = ['AddressOrLabel', 'LabelName', 'create_core_cli']


class LabelName(click.ParamType):
    """Parameter type that expects an existing label name."""
    name = "label_name"

    def __init__(self, asm: "Disassembler"):
        self.asm = asm

    def convert(self, value, param, ctx):
        if value not in self.asm.labels:
            self.fail(f"Label {value} not found", param, ctx)
        return value


class AddressOrLabel(click.ParamType):
    """
    Parameter type for an address. This address can be either the name
    of an existing label, or a valid address-like input. In case of the
    later, the detected bank cannot be unknown.
    """
    name = "address_or_label"

    def __init__(self, asm: "Disassembler"):
        self.asm = asm

    def convert(self, value, param, ctx) -> Address:
        if isinstance(value, str):
            if value in self.asm.labels:
                return self.asm.labels.lookup(value).address
            try:
                value = Address.parse(value)
            except ValueError as err:
                self.fail(str(err), param, ctx)

        assert isinstance(value, Address)
        if value.bank < 0:
            self.fail("Bank required for this range", param, ctx)
        return value


def create_core_cli(asm: "Disassembler") -> click.Group:

    @click.group()
    def ugb_core_cli():
        pass

    def address_arg(name="address"):
        return click.argument(name, type=AddressOrLabel(asm))

    # Base commands
    @ugb_core_cli.command()
    @click.argument("rom_path", type=click.File('rb'))
    def load_rom(rom_path: BinaryIO):
        asm.load_rom(rom_path)

    # Project commands
    @ugb_core_cli.group("project")
    def project_cli():
        pass

    @project_cli.command("save")
    @click.argument("name", default='')
    def project_save(name: str = ''):
        if name:
            asm.project_name = name
        save_project(asm)

    @project_cli.command("load")
    @click.argument("name", default='')
    def project_load(name: str = ''):
        if asm.is_loaded:
            raise ValueError("Project already loaded")
        if name:
            asm.project_name = name
        load_project(asm)

    # Manager sub-commands
    for mgr in asm.managers:
        ugb_core_cli.add_command(mgr.build_cli())

    # Section commands
    @ugb_core_cli.group("section")
    def section_cli():
        pass

    @section_cli.command("create")
    @address_arg()
    @click.argument("name")
    def section_create(address: Address, name: str):
        asm.sections.create(address, name)

    return ugb_core_cli
