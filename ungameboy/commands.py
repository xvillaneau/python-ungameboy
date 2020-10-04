from inspect import Parameter, signature
import shlex
from typing import TYPE_CHECKING, Callable, Dict, List, Tuple, Union

from .address import Address
from .project_save import save_project, load_project, import_plugin

if TYPE_CHECKING:
    from .dis.disassembler import Disassembler

__all__ = [
    'LabelName', 'UgbCommand', 'UgbCommandGroup', 'create_core_cli_v2',
]

Cmd = Union[str, Tuple[str]]


class LabelName(str):
    pass


class UgbCommand:
    """Handling code for a single command."""

    def __init__(self, asm: 'Disassembler', handler: Callable):
        self.args: List[Parameter] = []
        self.options: Dict[str, Parameter] = {}
        self.handler = handler
        self.asm = asm

        # Go through the arguments for the handler. For now, support is
        # limited to positional or keyword args. Keyword args with False
        # as default will be considered "flags" that can be specified at
        # the end of the call.
        for param in signature(handler).parameters.values():
            if param.kind is Parameter.KEYWORD_ONLY:
                if param.default is Parameter.empty:
                    raise TypeError("Keyword-only arg must have a default")
                self.options[param.name] = param

            elif param.kind is Parameter.POSITIONAL_OR_KEYWORD:
                if param.default is not Parameter.empty:
                    self.options[param.name] = param
                self.args.append(param)

            else:
                raise TypeError(f"Unsupported command arg type: {param}")

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

        return value

    def __call__(self, command: Cmd):
        args_queue = self.args.copy()
        args = {}

        if isinstance(command, str):
            command = command.strip()

        def get_head() -> str:
            nonlocal command
            if isinstance(command, str):
                if command.startswith(('"', "'")):
                    head, *command = shlex.split(command)
                else:
                    head, _, command = command.partition(' ')
                    command = command.lstrip()
            else:
                if not command:
                    raise TypeError("Ran out of arguments")
                head, *command = command
            return head

        def register(value, parameter: Parameter):
            name = parameter.name
            if name in args:
                raise TypeError(f"Argument {name} already defined")
            args[name] = self.process_arg(value, parameter)

        # Go through the positional arguments
        while command:
            arg = get_head()

            if arg.startswith("--"):
                arg = arg[2:]
                if arg not in self.options:
                    raise TypeError(f"Unrecognized argument: --{arg}")

                param = self.options[arg]
                if param.default is False:
                    register(True, param)
                else:
                    register(get_head(), param)

            else:
                if not args_queue:
                    raise TypeError(f"Extra unused argument: {arg}")
                register(arg, args_queue.pop(0))

        if any(param.default is Parameter.empty for param in args_queue):
            raise TypeError("Missing arguments")

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

    def get_handler(self, command: Cmd) -> Tuple[UgbCommand, Cmd]:
        if isinstance(command, str):
            instruction, _, command = command.strip().partition(' ')
            command.lstrip()
        else:
            instruction, *command = command

        handler = self.commands[instruction]
        if isinstance(handler, UgbCommandGroup):
            return handler.get_handler(command)
        else:
            return handler, command

    def __call__(self, command: Union[str, Tuple[str]]):
        handler, command = self.get_handler(command)
        return handler(command)


def create_core_cli_v2(asm: 'Disassembler') -> UgbCommandGroup:
    ugb_cli = UgbCommandGroup(asm, "ungameboy")
    project_cli = UgbCommandGroup(asm, "project")
    ugb_cli.add_group(project_cli)

    @ugb_cli.add_command("load-rom")
    def load_rom(rom_path: str):
        with open(rom_path, 'rb') as rom_file:
            asm.load_rom(rom_file)

    ugb_cli.add_command("import-plugin", import_plugin)

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
