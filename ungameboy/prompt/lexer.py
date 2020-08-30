from typing import TYPE_CHECKING, Tuple, Union

from ..address import Address
from ..data_types import Byte, IORef, Ref, Word, SPOffset
from ..dis import (
    AsmElement,
    DataRow,
    Instruction,
    Label,
    LabelOffset,
    RomElement,
    SpecialLabel,
)
from ..enums import Condition, DoubleRegister, Register, C

if TYPE_CHECKING:
    from .control import AsmControl

MARGIN = 4
HIGHLIGHT = ',ugb.hl'


def render_reference(
        elem: AsmElement, reference: Union[Address, Label, LabelOffset]
) -> Tuple[str, str]:
    if isinstance(reference, Label):
        scope_name = elem.scope.name if elem.scope else ''
        if reference.local_name and reference.global_name == scope_name:
            out = '.' + reference.local_name
        else:
            out = reference.name
        cls = 'label'
    elif isinstance(reference, LabelOffset):
        out = (
            f"{reference.label.name} "
            f"{'-' if reference.offset < 0 else '+'}"
            f"${reference.offset:x}"
        )
        cls = 'label'
    else:  # Address
        out = str(reference)
        cls = 'addr'
    return out, cls


def render_instruction(data: Instruction, control: "AsmControl"):
    instr = data.raw_instruction

    op_type = instr.type.value.lower()
    items = [(f'class:ugb.instr.op.{op_type}', op_type)]
    if not instr.args:
        return items

    def add(string, cls=''):
        if cls:
            cls = f'class:ugb.value.{cls}.{op_type}'
        items.append((cls, str(string)))

    for pos, arg in enumerate(instr.args):
        add(', ' if pos > 0 else ' ')

        if isinstance(arg, Ref):
            ref = arg.__class__
            arg = arg.target
            add('[')
        else:
            ref = None

        if (pos + 1 == instr.value_pos):
            arg = data.value

        # Arg can be: (Double)Register, Byte/Word/SignedByte/SPOffset,
        #   Label, Ref/IORef to any of the previous, condition, integer
        if ref is IORef and isinstance(arg, Byte):
            add(Word(arg + 0xff00), 'scalar')
        elif ref is IORef and arg is C:
            add(Word(0xff00), 'scalar')
            add(' + ')
            add('c', 'reg')
        elif isinstance(arg, (Register, DoubleRegister)):
            add(str(arg).lower(), 'reg')
        elif isinstance(arg, SPOffset):
            add('sp', 'reg')
            add(' + ')
            add(Byte(arg), 'scalar')
        elif isinstance(arg, int):
            add(arg, 'scalar')
        elif isinstance(arg, (Address, Label)):
            add(*render_reference(data, arg))
        elif isinstance(arg, Condition):
            add(str(arg).lower(), 'cond')
        elif isinstance(arg, SpecialLabel):
            add(arg.name, 'special')
        else:
            add(arg)

        if ref:
            add(']')

    reads = data.xrefs.reads
    writes = data.xrefs.writes_to
    if reads or writes:
        line_len = sum(len(s) for _, s in items)
        items.append(('', ' ' * max(22 - line_len, 2)))
        items.append(('class:ugb.xrefs', ';'))
        if reads is not None:
            reads = control.asm.context.address_context(data.address, reads)
            reads = 'Reads: ' + render_reference(data, reads)[0]
            items.extend([('', ' '), ('class:ugb.xrefs', reads)])
        if writes is not None:
            writes = control.asm.context.address_context(data.address, writes)
            writes = 'Writes: ' + render_reference(data, writes)[0]
            items.extend([('', ' '), ('class:ugb.xrefs', writes)])

    return items


def render_row(data: DataRow):
    line = []
    for item in data.values:
        if isinstance(item, (Address, Label)):
            item, cls = render_reference(data, item)
            cls = '.' + cls
        else:
            cls = ''
        line.extend([('class:ugb.value' + cls, str(item)), ('', ', ')])
    line.pop()

    return line


def render_binary(data: RomElement, control: "AsmControl"):
    bin_cls = 'class:ugb.bin'
    bin_hex = data.bytes.hex()

    bin_size = (
        max(data.data_block.row_size * 2, 6)
        if isinstance(data, DataRow)
        else 6
    )

    cursor = control.cursor
    if control.cursor_mode and data.address <= cursor < data.next_address:
        pos = (control.cursor.offset - data.address.offset) * 2
        if pos != 0:
            yield (bin_cls, bin_hex[:pos])
        yield (bin_cls + HIGHLIGHT, bin_hex[pos:pos + 2])
        if pos < len(bin_hex) - 2:
            yield (bin_cls, bin_hex[pos + 2:])
    else:
        yield (bin_cls, bin_hex)
    yield ('', ' ' * (bin_size - len(bin_hex) + 2))


def render_flags(data: RomElement, asm):
    flags = "C" if data.xrefs.calls else " "
    flags += "J" if data.xrefs.jumps_to else " "
    flags += "+" if asm.context.has_context(data.address) else " "
    return flags


def render_element(address: Address, control: "AsmControl"):
    lines = []

    elem = control.asm[address]

    if elem.section is not None:
        section = elem.section
        lines.append([
            ('class:ugb.section', 'SECTION'),
            ('', ' "'),
            ('class:ugb.section.name', section.name),
            ('', '", '),
            ('class:ugb.section.address', str(section.address)),
        ])

    for label in elem.labels:
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

    if isinstance(elem, RomElement):
        addr_cls = 'class:ugb.address'
        addr_cls += '.data' if isinstance(elem, DataRow) else ''
        if control.cursor_mode and elem.address == control.cursor_destination:
            addr_cls += HIGHLIGHT

        addr_str = str(elem.address)
        addr_items = [
            ('', ' ' * (MARGIN + 12 - len(addr_str))),
            (addr_cls, addr_str),
            ('', '  '),
            *render_binary(elem, control),
            ('class:ugb.flags', render_flags(elem, control.asm)),
            ('', ' '),
        ]

        addr_context = control.asm.context.address_context
        for call_orig in elem.xrefs.called_by:
            call_orig = addr_context(elem.address, call_orig, True)
            call_orig, _ = render_reference(elem, call_orig)
            lines.append([
                addr_items[0],
                ('class:ugb.xrefs', f"; Call from {call_orig}")
            ])
        for jump_orig in elem.xrefs.jumps_from:
            jump_orig = addr_context(elem.address, jump_orig, True)
            jump_orig, _ = render_reference(elem, jump_orig)
            lines.append([
                addr_items[0],
                ('class:ugb.xrefs', f"; Jump from {jump_orig}")
            ])

        if isinstance(elem, Instruction):
            lines.append([
                *addr_items,
                *render_instruction(elem, control),
            ])

        elif isinstance(elem, DataRow):
            if elem.row == 0:
                desc = (
                    elem.data_block.__class__.__name__ +
                    f' ({elem.data_block.size} bytes)'
                )
                lines.append([
                    addr_items[0],
                    ('class:ugb.data.header', '; ' + desc)
                ])
            lines.append([*addr_items, *render_row(elem)])

    return lines
