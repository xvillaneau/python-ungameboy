from inspect import Parameter, signature
import shlex
from typing import (
    TYPE_CHECKING, BinaryIO, Callable, Dict, List, Set, Tuple, Union
)

import click

from .address import Address
from .project_save import save_project, load_project

if TYPE_CHECKING:
    from .dis.disassembler import Disassembler

# __all__ = ['AddressOrLabel', 'ExtendedInt', 'LabelName', 'create_core_cli']


class LabelName(click.ParamType):
    """Parameter type that expects an existing label name."""
    name = "label_name"

    def __init__(self, asm: "Disassembler"):
        self.asm = asm

    def convert(self, value, param, ctx):
        if value not in self.asm.labels:
            self.fail(f"Label {value} not found", param, ctx)
        return value


class ExtendedInt(click.ParamType):
    """Integer parameter that also accepts hexadecimal input"""
    name = "extended_integer"

    def convert(self, value, param, ctx):
        if value is None:
            return value
        if isinstance(value, str):
            if value.startswith('0x'):
                value, base = value[2:], 16
            elif value.startswith('$'):
                value, base = value[1:], 16
            else:
                base = 10
            value = int(value, base=base)
        if not isinstance(value, int):
            self.fail("Invalid base 10 or 16 integer", param, ctx)
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

    return ugb_core_cli


class LongString(str):
    pass


class UgbCommand:
    """Handling code for a single command."""

    def __init__(self, asm: 'Disassembler', handler: Callable):
        self.args: List[Parameter] = []
        self.flags: Set[str] = set()
        self.handler = handler
        self.asm = asm

        # Go through the arguments for the handler. For now, support is
        # limited to positional or keyword args. Keyword args with False
        # as default will be considered "flags" that can be specified at
        # the end of the call.
        for param in signature(handler).parameters.values():
            if param.kind is not Parameter.POSITIONAL_OR_KEYWORD:
                raise TypeError(f"Unsupported command arg type: {param}")
            if param.default is False:
                self.flags.add(param.name)
            else:
                self.args.append(param)

    def process_arg(self, value, param: Parameter):
        """Apply type conversion to the argument"""
        if not isinstance(value, str):
            return value

        if param.annotation is Address:
            if value in self.asm.labels:
                return self.asm.labels.lookup(value).address
            try:
                value = Address.parse(value)
            except ValueError:
                raise TypeError(f"Not a valid address or label: {value}")

        if param.annotation is int:
            if value.startswith('0x'):
                value, base = value[2:], 16
            elif value.startswith('$'):
                value, base = value[1:], 16
            else:
                base = 10
            return int(value, base=base)

        if param.annotation is LongString:
            return LongString(value)

        return value

    def __call__(self, command: Union[str, Tuple[str]]):
        args_queue = self.args.copy()
        start_cmd = command
        args = {}

        if isinstance(command, str):
            command = command.strip()

        def get_head():
            nonlocal command
            if isinstance(command, str):
                head, _, command = command.partition(' ')
                command = command.lstrip()
            else:
                head, *command = command
            return head

        # Go through the positional arguments
        while args_queue:
            param = args_queue.pop(0)

            if not command:
                if param.default is Parameter.empty:
                    raise TypeError(f"Argument {param} missing in: {start_cmd}")
                continue

            # Special case if we expect a string with spaces.
            if param.annotation is LongString:
                if isinstance(command, str):
                    arg = command
                elif len(command) == 1:
                    arg = command[0]
                else:
                    # Reproduce shlex.join, which was introduced in Python 3.8
                    arg = ' '.join(map(shlex.quote, command)).strip()
                command = ''
            else:
                arg = get_head()

            args[param.name] = self.process_arg(arg, param)

        # Check for flags at the end
        while command:
            flag = get_head()
            if flag.startswith('--') and flag[2:] in self.flags:
                args[flag[2:]] = True
            else:
                raise TypeError(f"Unrecognized argument: {flag}")

        return self.handler(**args)


class UgbCommandGroup:
    def __init__(self, asm: 'Disassembler', name: str):
        self.asm = asm
        self.name = name
        self.commands: Dict[str, Union[UgbCommand, 'UgbCommandGroup']] = {}

    def add_command(self, name: str, handler: Callable = None):
        if handler is None:
            # Work as a decorator
            return lambda func: self.add_command(name, func)
        if name in self.commands:
            raise KeyError(f"Command {name} already exists")
        handler = UgbCommand(self.asm, handler)
        self.commands[name] = handler

    def add_group(self, group: 'UgbCommandGroup'):
        if group.name in self.commands:
            raise KeyError(f"Command {group.name} already exists")
        if not group.name:
            raise ValueError("A command sub-group must have a name")
        self.commands[group.name] = group

    def __call__(self, command: Union[str, Tuple[str]]):
        if isinstance(command, str):
            instruction, _, command = command.strip().partition(' ')
            command.lstrip()
        else:
            instruction, *command = command

        handler = self.commands[instruction]
        return handler(command)


def create_core_cli_v2(asm: 'Disassembler') -> UgbCommandGroup:
    ugb_cli = UgbCommandGroup(asm, "ungameboy")
    project_cli = UgbCommandGroup(asm, "project")
    ugb_cli.add_group(project_cli)

    @ugb_cli.add_command("load-rom")
    def load_rom(rom_path: LongString):
        with open(rom_path, 'rb') as rom_file:
            asm.load_rom(rom_file)

    # Project commands
    @project_cli.add_command("save")
    def project_save(name: str = ''):
        if name:
            asm.project_name = name
        save_project(asm)

    @project_cli.add_command("load")
    def project_load(name: str = ''):
        if asm.is_loaded:
            raise ValueError("Project already loaded")
        if name:
            asm.project_name = name
        load_project(asm)

    for mgr in asm.managers:
        ugb_cli.add_group(mgr.build_cli_v2())

    return ugb_cli
