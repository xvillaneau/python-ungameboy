import os
from pathlib import Path
import shlex

from .dis.binary_data import ROW_TYPES_NAMES, DataTable
from .dis.disassembler import Disassembler

PROJECTS_DIR = Path.home() / '.ungameboy' / 'projects'

TYPES_NAMES = {obj: name for name, obj in ROW_TYPES_NAMES}


def get_save_state(asm: "Disassembler"):
    if asm.rom is not None:
        yield ('load-rom', Path(asm.rom_path).resolve())

    for section in asm.sections.list_sections():
        yield (
            'section',
            'create',
            section.address,
            section.name,
        )

    for data_blk in asm.data.list_items():
        if isinstance(data_blk, DataTable):
            row = ','.join(TYPES_NAMES[obj] for obj in data_blk.row_struct)
            yield (
                'data',
                'create-table',
                data_blk.address,
                data_blk.rows,
                row,
            )
        else:
            yield (
                'data',
                'create-simple',
                data_blk.address,
                data_blk.size,
            )

    for label in asm.labels.list_items():
        yield (
            'label',
            'create',
            label.address,
            label.name,
        )

    for context in asm.context.list_context():
        if context.force_scalar:
            yield ('context', 'force-scalar', context.address)
        if context.bank >= 0:
            yield ('context', 'force-bank', context.address, context.bank)


def save_project(asm: "Disassembler"):
    if not asm.project_name:
        raise ValueError("Cannot save a project without name!")

    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    project_path = PROJECTS_DIR / f"{asm.project_name}.ugb.txt"

    with open(project_path, 'w', encoding='utf8') as proj_save:
        for command in get_save_state(asm):
            # Reproduce shlex.join, which was introduced in Python 3.8
            line = ' '.join(shlex.quote(str(item)) for item in command)
            proj_save.write(line + os.linesep)


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
