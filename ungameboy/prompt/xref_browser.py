from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout.controls import FormattedTextControl

from .key_bindings import create_xref_inspect_bindings
from ..address import Address
from ..dis import Label, LabelOffset

if TYPE_CHECKING:
    from .application import UGBApplication


@dataclass
class XRefBrowserState:
    address: Optional[Address] = None
    cursor: int = 0


def make_xrefs_control(ugb: 'UGBApplication'):
    asm = ugb.asm

    def get_xrefs_content():
        if ugb.xrefs.address is None:
            return []

        xrefs = asm.xrefs.get_xrefs(ugb.xrefs.address)
        calls = list(sorted(xrefs.called_by))
        jumps = list(sorted(xrefs.jumps_from))
        reads = list(sorted(xrefs.read_by))
        writes = list(sorted(xrefs.written_by))
        comment = asm.comments.blocks.get(ugb.xrefs.address, [])

        if not any([calls, jumps, reads, writes, comment]):
            return [('', 'No references found')]

        nl = ('', '\n')
        line_index = 0
        tokens = []

        if comment:
            for line in comment:
                tokens.extend([('class:ugb.comment', f'; {line}'), nl])
            tokens.append(nl)

        def display_xref(_addr):
            tokens.append(('', '  '))
            sel = ',ugb.hl' * (line_index == ugb.xrefs.cursor)
            tokens.append(('class:ugb.address' + sel, str(_addr)))

            name = asm.context.address_context(_addr, _addr, relative=True)
            if isinstance(name, Label):
                tokens.extend([
                    ('', ' ('),
                    ('class:ugb.value.label', name.name),
                    ('', ')'),
                ])
            elif isinstance(name, LabelOffset):
                offset = f"{'-' if name.offset < 0 else '+'}${name.offset:x}"
                tokens.extend([
                    ('', ' ('),
                    ('class:ugb.value.label', name.label.name),
                    ('', ' '),
                    ('class:ugb.value', offset),
                    ('', ')'),
                ])

            tokens.append(nl)

        if calls:
            tokens.extend([('', 'Called from:'), nl])
            for addr in calls:
                display_xref(addr)
                line_index += 1
            tokens.append(nl)
        if jumps:
            tokens.extend([('', 'Jumps from:'), nl])
            for addr in jumps:
                display_xref(addr)
                line_index += 1
            tokens.append(nl)
        if reads:
            tokens.extend([('', 'Read from:'), nl])
            for addr in reads:
                display_xref(addr)
                line_index += 1
            tokens.append(nl)
        if writes:
            tokens.extend([('', 'Written from:'), nl])
            for addr in writes:
                display_xref(addr)
                line_index += 1
            tokens.append(nl)

        if tokens:  # Remove last newlines
            tokens.pop()
            tokens.pop()

        return tokens

    def get_cursor_pos():
        """Used by PT to handle scrolling in the XREF browser"""
        if ugb.xrefs.address is None:
            return None

        line_pos = cursor = ugb.xrefs.cursor
        if cursor == 0:
            # Always return 0 at top of file (even if actual cursor is
            # lower), otherwise no amount of scrolling up would show it.
            return Point(0, 0)

        # Handle the offset caused by the comment/docstring
        doc_size = len(asm.comments.blocks.get(ugb.xrefs.address, []))
        line_pos += doc_size + doc_size > 0

        xrefs = asm.xrefs.get_xrefs(ugb.xrefs.address)
        n_calls = len(xrefs.called_by)
        n_jumps = len(xrefs.jumps_from)
        n_reads = len(xrefs.read_by)
        n_writes = len(xrefs.written_by)

        # For each section, if it exists:
        # - add 1 to account for the section name,
        # - add 1 more if there was any section before,
        # - if cursor not in that section, decrement and try next.

        line_pos += n_calls > 0
        if cursor < n_calls:
            return Point(0, line_pos)
        multi_section = n_calls > 0
        cursor -= n_calls

        line_pos += (n_jumps > 0) * (1 + multi_section)
        if cursor < n_jumps:
            return Point(0, line_pos)
        multi_section |= n_jumps > 0
        cursor -= n_jumps

        line_pos += (n_reads > 0) * (1 + multi_section)
        if cursor < n_reads:
            return Point(0, line_pos)
        multi_section |= n_reads > 0
        cursor -= n_reads

        line_pos += (n_writes > 0) * (1 + multi_section)
        if cursor < n_writes:
            return Point(0, line_pos)

        return None

    return FormattedTextControl(
        text=get_xrefs_content,
        show_cursor=False,
        focusable=True,
        key_bindings=create_xref_inspect_bindings(ugb),
        get_cursor_position=get_cursor_pos,
    )


def make_xrefs_title_function(ugb: 'UGBApplication'):

    def get_xrefs_title():
        address = ugb.xrefs.address
        if address is None:
            return 'No address selected'

        labels = ugb.asm.labels.get_labels(address)
        if labels:
            target = f'{labels[-1].name} ({address})'
        else:
            target = str(address)

        return f'XREFs for: {target}'

    return get_xrefs_title
