from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shlex
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .dis.disassembler import Disassembler

PROJECTS_DIR = Path.home() / '.ungameboy' / 'projects'
AUTOSAVE_PERIOD = timedelta(minutes=5)
AUTOSAVE_NUM = 3


def get_save_state(asm: "Disassembler"):
    if asm.rom is not None:
        yield ('load-rom', Path(asm.rom_path).resolve())

    for mgr in asm.managers:
        yield from mgr.save_items()


def autosave_project(asm: "Disassembler"):
    if not asm.project_name:
        return

    now = datetime.now(timezone.utc)
    if now <= asm.last_save + AUTOSAVE_PERIOD:
        return

    name = f"{asm.project_name}.ugb_autosave_{now:%Y-%m-%d-%H%M%S}.txt"
    save_to_file(asm, PROJECTS_DIR / name)
    asm.last_save = now

    current_saves = list(PROJECTS_DIR.glob('*.ugb_autosave_*.txt'))
    # Remove the old auto-saves
    current_saves.sort(reverse=True)
    for save in current_saves[AUTOSAVE_NUM:]:
        save.unlink()


def save_project(asm: "Disassembler"):
    if not asm.project_name:
        raise ValueError("Cannot save a project without name!")

    project_path = PROJECTS_DIR / f"{asm.project_name}.ugb.txt"
    save_to_file(asm, project_path)

    asm.last_save = datetime.now(timezone.utc)


def save_to_file(asm: "Disassembler", path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)

    with NamedTemporaryFile('w', encoding='utf8', delete=False) as tmp:
        for command in get_save_state(asm):
            # Reproduce shlex.join, which was introduced in Python 3.8
            line = ' '.join(shlex.quote(str(item)) for item in command)
            tmp.write(line + os.linesep)

    os.replace(tmp.name, path)


def load_project(asm: "Disassembler"):
    from .commands import create_core_cli

    if asm.is_loaded:
        raise ValueError("Project already loaded, start from empty state")
    if not asm.project_name:
        raise ValueError("Cannot load a nameless project!")

    project_path = PROJECTS_DIR / f"{asm.project_name}.ugb.txt"
    if not project_path.exists():
        raise ValueError(f"Project {asm.project_name} not found")

    cli = create_core_cli(asm)
    asm.reset()
    with open(project_path, 'r', encoding='utf8') as proj_read:
        for line in proj_read:
            args = shlex.split(line.strip())
            cli.main(args, "ungameboy", standalone_mode=False)
