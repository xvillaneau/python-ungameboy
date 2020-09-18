from typing import TYPE_CHECKING, List, Tuple, Union

from ..address import Address
from ..data_types import Byte, CgbColor, IORef, Ref, Word, SPOffset
from ..dis import (
    AsmElement,
    CartridgeHeader,
    DataBlock,
    DataRow,
    EmptyData,
    Instruction,
    Label,
    LabelOffset,
    RomElement,
    SpecialLabel,
)
from ..enums import Condition, DoubleRegister, Register, C

if TYPE_CHECKING:
    from .control import AsmControl

__all__ = ['AssemblyRender']

MARGIN = 4
HIGHLIGHT = ',ugb.hl'

FormatToken = Tuple[str, str]
FormattedLine = List[FormatToken]
FormattedText = List[FormattedLine]
Reference = Union[Address, Label, LabelOffset]


def spc(n) -> FormatToken:
    return ('', ' ' * n)


S1, S2, S4 = spc(1), spc(2), spc(4)


class AssemblyRender:
    MARGIN = 4
    LOC_MARGIN = 2
    COMMENT_LINE = 60
    SHOW_BLOCK_COMMENTS = True

    XREF_TYPES = {
        "call": ("calls", "called_by", "Calls", "Call from", "Calls from"),
        "jump": ("jumps_to", "jumps_from", "Jumps to", "Jump from", "Jumps from"),
    }

    def __init__(self, control: 'AsmControl'):
        self.ctrl = control
        self.app = control.app
        self.asm = control.asm

    def cursor_at(self, elem: AsmElement):
        return self.ctrl.cursor_mode and elem.address == self.ctrl.address

    def cursor_at_dest(self, elem: AsmElement):
        return (
            self.ctrl.cursor_mode and
            elem.address == self.ctrl.destination_address
        )

    def cursor_in(self, elem: AsmElement):
        return (
                self.ctrl.cursor_mode and
                elem.address <= self.ctrl.address < elem.next_address
        )

    def margin_at(self, address: Address) -> FormatToken:
        return spc(self.MARGIN + 12 - len(str(address)))

    @classmethod
    def render_reference(
            cls, elem: AsmElement, reference: Reference
    ) -> FormatToken:
        if isinstance(reference, Label):
            scope_name = elem.scope.name if elem.scope else ''
            if reference.local_name and reference.global_name == scope_name:
                out = '.' + reference.local_name
            else:
                out = reference.name
            value_type = 'label'
        elif isinstance(reference, LabelOffset):
            out = (
                f"{reference.label.name} "
                f"{'-' if reference.offset < 0 else '+'}"
                f"${reference.offset:x}"
            )
            value_type = 'label'
        else:  # Address
            out = str(reference)
            value_type = 'addr'
        return out, value_type

    def render_value(self, elem: AsmElement, value, suffix=''):
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
            add(*self.render_reference(elem, value))

        # Display the scalar values
        elif isinstance(value, int):
            if isinstance(value, SPOffset):
                add('sp', 'reg')
                add(' + ')
                value = Byte(value)
            elif isinstance(value, CgbColor):
                r, g, b = value.rgb_5
                color = f'#{r * 8:02x}{g * 8:02x}{b * 8:02x}'
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

    @classmethod
    def render_cartridge_header(cls, data: CartridgeHeader):
        kc, vc = 'class:ugb.data.key', 'class:ugb.data.value'

        header = data.metadata
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
            banks = 'No banks (32 KiB)'
        yield [(kc, '; ROM:'), spc(6), (vc, banks)]

        sram_size = f'{header.sram_size_kb:,} KiB'
        if header.sram_size_kb == 0:
            sram = 'n/a'
        elif header.sram_size_kb <= 8:
            sram = sram_size
        else:
            sram = f'{header.sram_size_kb // 8} banks ({sram_size})'
        yield [(kc, '; SRAM:'), spc(5), (vc, sram)]

    def render_address(self, elem: AsmElement) -> FormattedLine:
        addr_cls = 'class:ugb.address'
        addr_cls += '.data' if isinstance(elem, (DataRow, DataBlock)) else ''
        if self.cursor_at_dest(elem):
            addr_cls += HIGHLIGHT

        addr = elem.address
        return [self.margin_at(addr), (addr_cls, str(addr)), S2]

    def render_bytes(self, elem: RomElement) -> FormattedLine:
        bin_cls = 'class:ugb.bin'
        bin_hex = elem.bytes.hex()

        bin_size = (
            max(elem.data.row_size * 2, 6)
            if isinstance(elem, DataRow)
            else 6
        )

        line = []
        if self.cursor_in(elem):
            pos = (self.ctrl.address.offset - elem.address.offset) * 2
            if pos != 0:
                line.append((bin_cls, bin_hex[:pos]))
            line.append((bin_cls + HIGHLIGHT, bin_hex[pos:pos + 2]))
            if pos < len(bin_hex) - 2:
                line.append((bin_cls, bin_hex[pos + 2:]))
        else:
            line.append((bin_cls, bin_hex))
        line.append(spc(bin_size - len(bin_hex) + 2))
        return line

    def render_flags(self, elem: AsmElement) -> FormattedLine:
        xr = elem.xrefs
        flags = {
            'x': any([xr.calls, xr.jumps_to, xr.reads, xr.writes_to]),
            '+': self.asm.context.has_context(elem.address),
        }
        flags_str = ''.join(
            flag if cond else ' '
            for flag, cond in flags.items()
        )
        return [('class:ugb.flags', flags_str), S1]

    def _render_ref_lines(self, elem: AsmElement, name: str) -> FormattedText:
        _, attr, _, single, plural = self.XREF_TYPES[name]
        refs = getattr(elem.xrefs, attr)

        lines = []
        if len(refs) > 3:
            lines.append(f"; {plural} {len(refs)} places")
        else:
            get_context = self.asm.context.address_context
            for ref in refs:
                ref = get_context(elem.address, ref, relative=True)
                ref, _ = self.render_reference(elem, ref)
                lines.append(f"; {name} from {ref}")

        margin = self.margin_at(elem.address)
        return [[margin, ('class:ugb.xrefs', line)] for line in lines]

    def render_block_xrefs(self, elem: AsmElement) -> FormattedText:
        return [
            *self._render_ref_lines(elem, "call"),
            *self._render_ref_lines(elem, "jump"),
        ]

    def render_block_comment(self, elem: AsmElement) -> FormattedText:
        if not self.SHOW_BLOCK_COMMENTS:
            return []
        margin = self.margin_at(elem.address)
        return [
            [margin, ('class:ugb.comment', f'; {line}')]
            for line in elem.block_comment
        ]

    def render_inline_xrefs(self, elem: AsmElement) -> FormattedLine:
        reads = elem.xrefs.reads
        writes = elem.xrefs.writes_to
        if isinstance(elem, RomElement):
            reads = reads if reads != elem.dest_address else None
            writes = writes if writes != elem.dest_address else None

        line = []
        if reads or writes:
            line.append(('class:ugb.xrefs', ';'))

        if reads is not None:
            reads = self.asm.context.address_context(elem.address, reads)
            reads = 'Reads: ' + self.render_reference(elem, reads)[0]
            line.extend([S1, ('class:ugb.xrefs', reads)])

        if writes is not None:
            writes = self.asm.context.address_context(elem.address, writes)
            writes = 'Writes: ' + self.render_reference(elem, writes)[0]
            line.extend([S1, ('class:ugb.xrefs', writes)])

        return line

    def render_labels(self, elem: AsmElement) -> FormattedText:
        cls = 'class:ugb.label.'
        lines = []
        for label in elem.labels:
            if label.local_name:
                pre = [spc(self.LOC_MARGIN), ('', '.')]
                line = [*pre, (cls + 'local', label.local_name)]
            else:
                line = [(cls + 'global', label.name), ('', ':')]
            lines.append(line)
        return lines

    def render_instruction(self, elem: Instruction) -> FormattedLine:
        instr = elem.raw_instruction

        op_type = instr.type.value.lower()
        items = [
            *self.render_address(elem),
            *self.render_bytes(elem),
            *self.render_flags(elem),
            (f'class:ugb.instr.op.{op_type}', op_type),
        ]

        for pos, arg in enumerate(instr.args):
            if (pos + 1 == instr.value_pos):
                if isinstance(arg, Ref):
                    arg = arg.cast(elem.value)
                else:
                    arg = elem.value

            items.append(('', ', ' if pos > 0 else ' '))
            items.extend(self.render_value(elem, arg, op_type))

        return items

    def add_inline_xrefs(self, elem: AsmElement, line: FormattedLine):
        inline_xrefs = self.render_inline_xrefs(elem)
        if inline_xrefs:
            line_len = sum(len(s) for _, s in line)
            line.append(spc(max(self.COMMENT_LINE - line_len, 2)))
            line.extend(inline_xrefs)

    def add_inline_comment(self, elem: AsmElement, line: FormattedLine):
        cls = 'class:ugb.comment'

        if self.ctrl.comment_mode and elem.address == self.ctrl.address:
            line_len = sum(len(s) for _, s in line)
            line.append(spc(max(self.COMMENT_LINE - line_len, 2)))

            comment, pos = self.ctrl.comment_buffer, self.ctrl.cursor_x
            pre, post = '; ' + comment[:pos], comment[pos + 1:]
            cursor = comment[pos] if pos < len(comment) else ' '

            line.extend([(cls, pre), (cls + HIGHLIGHT, cursor), (cls, post)])

        elif elem.comment:
            line_len = sum(len(s) for _, s in line)
            line.append(spc(max(self.COMMENT_LINE - line_len, 2)))

            line.append((cls, f"; {elem.comment}"))

    def render_data(self, elem: Union[DataBlock, DataRow]) -> FormattedText:
        if elem.data.description:
            desc = elem.data.description
        else:
            desc = elem.data.__class__.__name__
        desc = f'; {desc} ({elem.data.size} bytes)'

        lines = []
        cls = 'class:ugb.data.header'
        margin = self.margin_at(elem.address)

        if isinstance(elem, DataRow):
            if elem.row == 0:
                lines.append([margin, (cls, desc)])

            line = [
                *self.render_address(elem),
                *self.render_bytes(elem),
                *self.render_flags(elem),
            ]
            for item in elem.values:
                line.extend(self.render_value(elem, item))
                line.append(('', ', '))
            line.pop()
            lines.append(line)

        elif isinstance(elem, DataBlock):
            if isinstance(elem.data, EmptyData):
                cls = 'class:ugb.data.empty'
            if self.cursor_in(elem):
                cls += HIGHLIGHT
            lines.append([*self.render_address(elem), (cls, desc)])

            if isinstance(elem.data, CartridgeHeader):
                block_content = self.render_cartridge_header(elem.data)
            else:
                block_content = []
            for items in block_content:
                lines.append([margin, ('', '    '), *items])

        return lines

    def render(self, address: Address) -> FormattedText:
        elem = self.asm[address]
        lines = [
            *self.render_labels(elem),
            *self.render_block_xrefs(elem),
            *self.render_block_comment(elem),
        ]

        if isinstance(elem, Instruction):
            line = self.render_instruction(elem)
            self.add_inline_xrefs(elem, line)
            self.add_inline_comment(elem, line)
            lines.append(line)

        elif isinstance(elem, (DataBlock, DataRow)):
            lines.extend(self.render_data(elem))

        return lines
