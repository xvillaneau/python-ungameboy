from typing import TYPE_CHECKING

from ..address import Address
from ..data_types import Byte, IORef, Ref, Word, SPOffset
from ..disassembler import (
    AsmElement,
    DataRow,
    Instruction,
    RomElement,
    SpecialLabel,
)
from ..enums import Condition, DoubleRegister, Register, C
from ..labels import Label

if TYPE_CHECKING:
    from .control import AsmControl

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

        ctx = data.context
        if (
                not ctx.force_scalar and
                pos + 1 == instr.value_pos and
                ctx.value_symbol is not None
        ):
            arg = ctx.value_symbol

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
        elif isinstance(arg, SpecialLabel):
            add(arg.name, 'special')
        else:
            add(arg)

        if ref:
            add(']')

    return items


def render_row(data: DataRow):
    block = data.data_block
    line = []
    for item in block[data.row]:
        line.extend([('', str(item)), ('', ', ')])
    line.pop()

    return line


def render_element(data: AsmElement, control: "AsmControl"):
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

    cursor_cls = ''
    if control.cursor_mode:
        if data.address == control.cursor:
            cursor_cls = ',ugb.cursor'
        elif data.address == control.cursor_destination:
            cursor_cls = ',ugb.cursor.dest'
    addr_cls = '.data' if isinstance(data, DataRow) else ''

    addr_str = str(data.address)
    addr_items = [
        ('', ' ' * (MARGIN + 12 - len(addr_str))),
        ('class:ugb.address' + addr_cls + cursor_cls, addr_str)
    ]

    if isinstance(data, RomElement):
        _size = (
            max(data.data_block.row_size * 2, 6)
            if isinstance(data, DataRow)
            else 6
        )
        addr_items.append(('', '  '))
        addr_items.append(('class:ugb.bin', f'{data.bytes.hex():<{_size}}'))
        addr_items.append(('', '  '))

    if isinstance(data, Instruction):
        lines.append([
            *addr_items,
            *render_instruction(data),
        ])

    elif isinstance(data, DataRow):
        if data.row == 0:
            desc = (
                data.data_block.__class__.__name__ +
                f' ({data.data_block.size} bytes)'
            )
            lines.append([
                addr_items[0],
                ('class:ugb.data.header', '; ' + desc)
            ])
        lines.append([*addr_items, *render_row(data)])

    return lines
