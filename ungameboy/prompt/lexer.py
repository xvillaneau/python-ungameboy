from typing import TYPE_CHECKING, Tuple, Union

from ..address import Address
from ..data_types import Byte, CgbColor, IORef, Ref, Word, SPOffset
from ..dis import (
    AsmElement,
    CartridgeHeader,
    DataBlock,
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


def spc(n):
    return ('', ' ' * n)


S1, S2, S4 = spc(1), spc(2), spc(4)


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


def render_value(elem: AsmElement, value, suffix=''):
    items = []

    def add(item, cls=''):
        if cls:
            cls = f'class:ugb.value.{cls}.{suffix}'.rstrip('.')
        items.append((cls, str(item)))

    if isinstance(value, Ref):
        ref = value.__class__
        value = value.target
        add('[')
    else:
        ref = None

    # Handle IO references separately, they're weird
    if ref is IORef and isinstance(value, Byte):
        add(Word(value + 0xff00), 'scalar')
    elif ref is IORef and value is C:
        add(Word(0xff00), 'scalar')
        add(' + ')
        add('c', 'reg')

    # Registers are very common, handle those first
    elif isinstance(value, (Register, DoubleRegister)):
        add(str(value).lower(), 'reg')

    # Then, addresses and labels
    elif isinstance(value, (Address, Label)):
        add(*render_reference(elem, value))

    # Display the scalar values
    elif isinstance(value, int):
        if isinstance(value, SPOffset):
            add('sp', 'reg')
            add(' + ')
            value = Byte(value)
        elif isinstance(value, CgbColor):
            r, g, b = value.rgb_5
            color = f'#{r*8:02x}{g*8:02x}{b*8:02x}'
            items.append((f'fg:{color}', '\u25a0'))
            items.append(S1)
        add(value, 'scalar')

    # Various stuff last
    elif isinstance(value, Condition):
        add(str(value).lower(), 'cond')
    elif isinstance(value, SpecialLabel):
        add(value.name, 'special')
    else:
        add(value)

    if ref:
        add(']')

    return items


def render_instruction(data: Instruction, control: "AsmControl"):
    instr = data.raw_instruction

    op_type = instr.type.value.lower()
    items = [(f'class:ugb.instr.op.{op_type}', op_type)]
    if not instr.args:
        return items

    for pos, arg in enumerate(instr.args):
        if (pos + 1 == instr.value_pos):
            if isinstance(arg, Ref):
                arg = arg.cast(data.value)
            else:
                arg = data.value

        items.append(('', ', ' if pos > 0 else ' '))
        items.extend(render_value(data, arg, op_type))

    reads = data.xrefs.reads
    reads = reads if reads != data.dest_address else None
    writes = data.xrefs.writes_to
    writes = writes if writes != data.dest_address else None
    if reads or writes:
        line_len = sum(len(s) for _, s in items)
        items.append(spc(max(22 - line_len, 2)))
        items.append(('class:ugb.xrefs', ';'))

        if reads is not None:
            reads = control.asm.context.address_context(data.address, reads)
            reads = 'Reads: ' + render_reference(data, reads)[0]
            items.extend([S1, ('class:ugb.xrefs', reads)])

        if writes is not None:
            writes = control.asm.context.address_context(data.address, writes)
            writes = 'Writes: ' + render_reference(data, writes)[0]
            items.extend([S1, ('class:ugb.xrefs', writes)])

    return items


def render_row(data: DataRow):
    line = []
    for item in data.values:
        line.extend(render_value(data, item))
        line.append(('', ', '))
    line.pop()

    return line


def render_data_block(elem: DataBlock):
    if isinstance(elem.data, CartridgeHeader):
        kc, vc = 'class:ugb.data.key', 'class:ugb.data.value'

        header = elem.data.metadata
        yield [(kc, '; Name:'), spc(5), (vc, header.title)]

        hardware = []
        if header.cgb_flag in ('dmg', 'both'):
            hardware.append('DMG')
        if header.cgb_flag in ('cgb', 'both'):
            hardware.append('CGB')
        if header.sgb_flag:
            hardware.append('SGB')
        yield [(kc, '; Hardware:'), spc(1), (vc, ', '.join(hardware))]

        if header.rom_banks > 0:
            size = header.rom_banks * 16
            banks = f'{header.rom_banks} banks ({size:,} KiB)'
        else:
            banks = f'No banks (32 KiB)'
        yield [(kc, '; ROM:'), spc(6), (vc, banks)]

        sram_size = f'{header.sram_size_kb:,} KiB'
        if header.sram_size_kb == 0:
            sram = 'n/a'
        elif header.sram_size_kb <= 8:
            sram = sram_size
        else:
            sram = f'{header.sram_size_kb // 8} banks ({sram_size})'
        yield [(kc, '; SRAM:'), spc(5), (vc, sram)]


def render_binary(data: RomElement, control: "AsmControl"):
    bin_cls = 'class:ugb.bin'
    bin_hex = data.bytes.hex()

    bin_size = (
        max(data.data.row_size * 2, 6)
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
    yield spc(bin_size - len(bin_hex) + 2)


def render_flags(data: RomElement, asm):
    xr = data.xrefs
    flags = {
        'x': any([xr.calls, xr.jumps_to, xr.reads, xr.writes_to]),
        '+': asm.context.has_context(data.address),
    }
    return ''.join(flag if cond else ' ' for flag, cond in flags.items())


def render_element(address: Address, control: "AsmControl"):
    lines = []
    elem = control.asm[address]

    def render_xrefs(refs, name):
        if len(refs) > 3:
            msg = f"; {name}s from {len(refs)} places"
            yield ('class:ugb.xrefs', msg)
            return
        get_context = control.asm.context.address_context
        for ref in refs:
            ref = get_context(elem.address, ref, relative=True)
            ref, _ = render_reference(elem, ref)
            yield ('class:ugb.xrefs', f"; {name} from {ref}")

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
        addr_cls += '.data' if isinstance(elem, (DataRow, DataBlock)) else ''
        if control.cursor_mode and elem.address == control.cursor_destination:
            addr_cls += HIGHLIGHT

        addr_str = str(elem.address)
        margin = spc(MARGIN + 12 - len(addr_str))

        addr_items = [margin, (addr_cls, addr_str), S2]
        bin_items = render_binary(elem, control)
        flag_items = [
            ('class:ugb.flags', render_flags(elem, control.asm)), S1
        ]

        calls, jumps = elem.xrefs.called_by, elem.xrefs.jumps_from
        lines.extend([margin, tok] for tok in render_xrefs(calls, 'Call'))
        lines.extend([margin, tok] for tok in render_xrefs(jumps, 'Jump'))

        if isinstance(elem, Instruction):
            lines.append([
                *addr_items, *bin_items, *flag_items,
                *render_instruction(elem, control),
            ])

        elif isinstance(elem, DataRow):
            if elem.row == 0:
                if elem.data.description:
                    desc = elem.data.description
                else:
                    desc = elem.data.__class__.__name__
                desc = f'; {desc} ({elem.data.size} bytes)'
                lines.append([margin, ('class:ugb.data.header', desc)])

            lines.append([
                *addr_items, *bin_items, *flag_items, *render_row(elem)
            ])

        elif isinstance(elem, DataBlock):
            if elem.data.description:
                desc = elem.data.description
            else:
                desc = elem.data.__class__.__name__
            desc = f'; {desc} ({elem.data.size} bytes)'

            cls = 'class:ugb.data.header'
            if elem.address <= control.cursor < elem.next_address:
                cls += HIGHLIGHT
            lines.append([*addr_items, (cls, desc)])

            for items in render_data_block(elem):
                lines.append([margin, ('', '    '), *items])

    return lines
