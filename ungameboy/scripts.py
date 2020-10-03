from functools import partial
from importlib import import_module
from typing import TYPE_CHECKING, Any, Callable, Dict

from .commands import UgbCommandGroup

if TYPE_CHECKING:
    from .dis import Disassembler


class ScriptsManager:
    def __init__(self, asm: "Disassembler"):
        self.asm = asm
        self.scripts: Dict[str, Dict[str, Callable]] = {}

    def discover_scripts(self, module_name: str):
        module = import_module(module_name)
        _, _, mod_name = module.__name__.rpartition('.')
        if mod_name in self.scripts:
            raise KeyError(f"Script namespace {mod_name} already exists")

        self.scripts[mod_name] = {
            func_name: obj
            for func_name, obj in module.__dict__.items()
            if hasattr(obj, '__call__') and hasattr(obj, 'ugb_script')
        }

    def get_commands(self) -> UgbCommandGroup:
        run_cli = UgbCommandGroup(self.asm, "run")
        for group, calls in self.scripts.items():
            group_cli = UgbCommandGroup(self.asm, group)
            for name, call in calls.items():
                group_cli.add_command(name, partial(call, self.asm))
            run_cli.add_group(group_cli)

        scripts_cli = UgbCommandGroup(self.asm, "script")
        scripts_cli.add_group(run_cli)
        return scripts_cli


def asm_script(func: Callable[["Disassembler", Any], Any]):
    func.ugb_script = "asm"
    return func
