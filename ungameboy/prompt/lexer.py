
from ..assembly_models import AsmElement, DataBlock, Instruction
from ..data_types import Byte, IORef, Ref, Word, SPOffset
from ..enums import Condition, DoubleRegister, Register, C
from ..labels import Label

MARGIN = ('', '    ')


def render_instruction(data: Instruction):
    instr = data.raw_instruction

    op_type = instr.type.value.lower()
    items = [(f'class:ugb.instr.op.{op_type}', op_type)]
    if not instr.args:
        return items

    def add(string, cls=''):
        if cls:
            cls = f'class:ugb.instr.{cls}'
        items.append((cls, str(string)))

    for pos, arg in enumerate(instr.args):
        add(', ' if pos > 0 else ' ')

        if isinstance(arg, Ref):
            ref = arg.__class__
            arg = arg.target
            add('[')
        else:
            ref = None

        if pos + 1 == instr.value_pos and data.value_symbol is not None:
            arg = data.value_symbol

        # Arg can be: (Double)Register, Byte/Word/SignedByte/SPOffset,
        #   Label, Ref/IORef to any of the previous, condition, integer
        if ref is IORef and isinstance(arg, Byte):
            add(Word(arg + 0xff00), 'value')
        elif ref is IORef and arg is C:
            add(Word(0xff00), 'value')
            add(' + ')
            add('c', 'reg')
        elif isinstance(arg, (Register, DoubleRegister)):
            add(str(arg).lower(), 'reg')
        elif isinstance(arg, SPOffset):
            add('sp', 'reg')
            add(' + ')
            add(Byte(arg), 'value')
        elif isinstance(arg, int):
            add(arg, 'value')
        elif isinstance(arg, Label):
            add(arg.name, 'label')
        elif isinstance(arg, Condition):
            add(str(arg).lower(), 'cond')
        else:
            add(arg)

        if ref:
            add(']')

    return items


def render_data(data: AsmElement):
    lines = []

    for label in data.labels:
        lines.append([
            ('class:ugb.label.global', label.name),
            ('', ':'),
        ])

    if isinstance(data, Instruction):
        instr = data.raw_instruction
        lines.append([
            MARGIN,
            ('class:ugb.address', f'{instr.address!s:>12}'),
            ('', '  '),
            ('class:ugb.bin', f'{instr.bytes.hex():<6}'),
            ('', '  '),
            *render_instruction(data),
        ])

    elif isinstance(data, DataBlock):
        lines.append([
            MARGIN,
            ('class:ugb.address', f'{data.address}'),
            ('', '  '),
            ('class:ugb.data.desc', data.name),
        ])
        lines.append([
            MARGIN,
            ('', '  -> '),
            ('class:ugb.address', f'{data.next_address - 1}'),
            ('', ' '),
            ('class:ugb.data.size', f'(${data.size:02x} bytes)')
        ])

    return lines
