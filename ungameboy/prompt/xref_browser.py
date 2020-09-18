from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

from prompt_toolkit.layout.controls import FormattedTextControl

from .key_bindings import create_xref_inspect_bindings
from ..address import Address
from ..dis import Label, LabelOffset

if TYPE_CHECKING:
    from .application import DisassemblyEditor


@dataclass
class XRefBrowserState:
    address: Optional[Address] = None
    cursor: int = 0


def make_xrefs_control(app: 'DisassemblyEditor'):

    def get_xrefs_content():
        if app.xrefs.address is None:
            return []

        xrefs = app.disassembler.xrefs.get_xrefs(app.xrefs.address)
        calls = list(sorted(xrefs.called_by))
        jumps = list(sorted(xrefs.jumps_from))
        reads = list(sorted(xrefs.read_by))
        writes = list(sorted(xrefs.written_by))

        if not any([calls, jumps, reads, writes]):
            return [('', 'No references found')]

        nl = ('', '\n')
        line_index = 0
        tokens = []

        def display_xref(_addr):
            tokens.append(('', '  '))
            sel = ',ugb.hl' * (line_index == app.xrefs.address)
            tokens.append(('class:ugb.address' + sel, str(_addr)))

            name = app.disassembler.context.address_context(
                _addr, _addr, relative=True
            )
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

    return FormattedTextControl(
        text=get_xrefs_content,
        show_cursor=False,
        focusable=True,
        key_bindings=create_xref_inspect_bindings(app),
    )


def make_xrefs_title_function(app: 'DisassemblyEditor'):

    def get_xrefs_title():
        address = app.xrefs.address
        if address is None:
            return 'No address selected'

        labels = app.disassembler.labels.get_labels(address)
        if labels:
            target = f'{labels[-1].name} ({address})'
        else:
            target = str(address)

        return f'XREFs for: {target}'

    return get_xrefs_title
