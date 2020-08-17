import shlex

from .address import Address
from .disassembler import Disassembler

COMMANDS = {}


def eval_and_run(asm: Disassembler, command: str):
    if not command:
        raise ValueError()
    tokens = shlex.split(command)
    command_tree = COMMANDS
    while isinstance(command_tree, dict):
        if tokens[0] not in command_tree:
            raise ValueError()
        command_tree = command_tree[tokens[0]]
        tokens.pop(0)
    command = command_tree

    address = Address.parse(tokens[0])
    try:
        arg = int(tokens[1])
    except ValueError:
        arg = tokens[1]

    command(asm, address, arg)


def register(name: str):
    command_tree = name.split('.')

    def decorator(func):
        cmd_register = COMMANDS
        for cmd in command_tree[:-1]:
            cmd_register = cmd_register.setdefault(cmd, {})
            if not isinstance(cmd_register, dict):
                raise ValueError(f"Colliding command namespace at {name}")
        cmd_register[command_tree[-1]] = func
        return func

    return decorator


@register('data.create')
def data_create(asm: Disassembler, address: Address, length: int = 1):
    asm.data.create(address, length)


@register('data.rename')
def data_rename(asm: Disassembler, address: Address, name: str):
    data = asm.data.get_data(address)
    if data is None:
        return
    data.description = name


@register('label.create')
def label_create(asm: Disassembler, address: Address, name: str):
    asm.labels.create(address, name)
