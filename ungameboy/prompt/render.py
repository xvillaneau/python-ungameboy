
from ..data_block import DataBlock
from ..disassembler import ViewItem
from ..instructions import Instruction

MARGIN = ('', '    ')


def render_data(data: ViewItem):
    lines = []
    data = data.data

    if isinstance(data.binary, Instruction):
        instr = data.binary
        lines.append([
            MARGIN,
            ('class:ugb.address', f'{instr.address}'),
            ('', '  '),
            ('class:ugb.bin', f'{instr.bytes.hex():<6}'),
            ('', '  '),
            ('', str(instr)),
        ])

    elif isinstance(data.binary, DataBlock):
        block = data.binary
        lines.append([
            MARGIN,
            ('class:ugb.address', f'{block.address}'),
            ('', '  '),
            ('class:ugb.data.desc', block.description),
        ])
        lines.append([
            MARGIN,
            ('', '  -> '),
            ('class:ugb.address', f'{block.next_address - 1}'),
            ('', ' '),
            ('class:ugb.data.size', f'(${block.length:2x} bytes)')
        ])

    return lines
