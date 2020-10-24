from functools import partial
from typing import TYPE_CHECKING, Any, Callable

from .commands import UgbCommandGroup
from .dis.manager_base import AsmManager

if TYPE_CHECKING:
    from .dis import Disassembler

SCRIPTS = {}


class ScriptsManager(AsmManager):

    def __init__(self, asm: "Disassembler"):
        super().__init__(asm)

    def build_cli_v2(self) -> UgbCommandGroup:
        scripts_cli = UgbCommandGroup(self.asm, "script")

        run_cli = scripts_cli.create_group("run")
        for name, call in SCRIPTS.items():
            run_cli.add_command(name, partial(call, self.asm))

        return scripts_cli

    def reset(self):
        pass

    def save_items(self):
        return ()


def asm_script(name: str):

    def decorator(func: Callable[["Disassembler", Any], Any]):
        existing = SCRIPTS.get(name)
        if existing is None:
            SCRIPTS[name] = func
        elif existing is not func:
            raise KeyError("Script {} already defined")
        return func

    return decorator
