
from ..disassembler import AsmData, DataBlock, Instruction


def render_data(data: AsmData):
    lines = []

    if isinstance(data.binary, Instruction):
        instr = data.binary
        lines.append([
            ('class:ugb.address', f'{instr.address:07x}'),
            ('', '  '),
            ('class:ugb.bin', f'{instr.bytes.hex():<6}'),
            ('', '  '),
            ('', str(instr)),
        ])

    elif isinstance(data.binary, DataBlock):
        block = data.binary
        lines.append([
            ('class:ugb.address', f'{block.address:07x}'),
            ('', '  '),
            ('class:ugb.data.desc', block.description),
        ])
        lines.append([
            ('', '  -> '),
            ('class:ugb.address', f'{block.next_address - 1:07x}'),
            ('', ' '),
            ('class:ugb.data.size', f'(${block.length:2x} bytes)')
        ])

    return lines
