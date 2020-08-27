from typing import BinaryIO, TYPE_CHECKING

import click

from .address import Address
from .project_save import save_project, load_project

if TYPE_CHECKING:
    from .disassembler import Disassembler

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

    address_arg = AddressOrLabel(asm)
    label_arg = LabelName(asm)

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

    # Data commands
    @ugb_core_cli.group("data")
    def data_cli():
        pass

    @data_cli.command("create")
    @click.argument("address", type=address_arg)
    @click.argument("size", type=int, default=1)
    @click.argument("name", default='')
    def data_create(address: Address, size=1, name=''):
        asm.data.create(address, size, name)

    @data_cli.command("rename")
    @click.argument("address", type=address_arg)
    @click.argument("name", default='')
    def data_rename(address: Address, name=''):
        data = asm.data.get_data(address)
        if data is None:
            return
        data.description = name

    # Label commands
    @ugb_core_cli.group("label")
    def label_cli():
        pass

    @label_cli.command("create")
    @click.argument("address", type=address_arg)
    @click.argument("name")
    def label_create(address: Address, name: str):
        asm.labels.create(address, name)

    @label_cli.command("rename")
    @click.argument("old_name", type=label_arg)
    @click.argument("new_name")
    def label_rename(old_name: str, new_name: str):
        asm.labels.rename(old_name, new_name)

    @label_cli.command("delete")
    @click.argument("name", type=label_arg)
    def label_delete(name: str):
        asm.labels.delete(name)

    # Section commands
    @ugb_core_cli.group("section")
    def section_cli():
        pass

    @section_cli.command("create")
    @click.argument("address", type=address_arg)
    @click.argument("name")
    def section_create(address: Address, name: str):
        asm.sections.create(address, name)

    return ugb_core_cli
