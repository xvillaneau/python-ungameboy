from typing import Optional

from ..address import Address
from ..data_types import Byte, IORef, Ref, Word, SPOffset
from ..disassembler import AsmElement, DataBlock, Instruction
from ..enums import Condition, DoubleRegister, Register, C
from ..labels import Label

MARGIN = 4


def render_instruction(data: Instruction):
    instr = data.raw_instruction

    op_type = instr.type.value.lower()
    items = [(f'class:ugb.instr.op.{op_type}', op_type)]
    if not instr.args:
        return items

    def add(string, cls=''):
        if cls:
            cls = f'class:ugb.instr.{cls}.{op_type}'
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
            if arg.local_name != '' and arg.global_name == data.scope:
                add(f'.{arg.local_name}', 'label')
            else:
                add(arg.name, 'label')
        elif isinstance(arg, Condition):
            add(str(arg).lower(), 'cond')
        elif isinstance(arg, Address):
            add(arg, 'addr')
        else:
            add(arg)

        if ref:
            add(']')

    return items


def render_data(data: AsmElement, cursor: Optional[Address] = None):
    lines = []

    if data.section_start is not None:
        section = data.section_start
        lines.append([
            ('class:ugb.section', 'SECTION'),
            ('', ' "'),
            ('class:ugb.section.name', section.name),
            ('', '", '),
            ('class:ugb.section.address', str(section.address)),
        ])

    for label in data.labels:
        if label.local_name:
            lines.append([
                ('', '  .'),
                ('class:ugb.label.local', label.local_name),
            ])
        else:
            lines.append([
                ('class:ugb.label.global', label.name),
                ('', ':'),
            ])

    cursor_cls = ",ugb.cursor" if data.address == cursor else ''
    addr_str = str(data.address)
    addr_items = [
        ('', ' ' * (MARGIN + 12 - len(addr_str))),
        ('class:ugb.address' + cursor_cls, addr_str)
    ]

    if isinstance(data, Instruction):
        instr = data.raw_instruction
        lines.append([
            *addr_items,
            ('', '  '),
            ('class:ugb.bin', f'{instr.bytes.hex():<6}'),
            ('', '  '),
            *render_instruction(data),
        ])

    elif isinstance(data, DataBlock):
        block_end = data.next_address.memory_address - 1
        lines.append([
            *addr_items,
            ('', ' \u2192 '),
            ('class:ugb.address', f'{block_end:04x}'),
        ])
        lines.append([
            ('', ' ' * (MARGIN + 4)),
            ('class:ugb.data.name', data.name),
            ('', ' ('),
            ('class:ugb.data.size', f'{data.size} bytes'),
            ('', ')'),
        ])

    return lines
