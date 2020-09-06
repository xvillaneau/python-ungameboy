from typing import TYPE_CHECKING, Optional

from prompt_toolkit.layout.controls import FormattedTextControl

from .key_bindings import create_xref_inspect_bindings
from ..address import Address
from ..dis import Label, LabelOffset

if TYPE_CHECKING:
    from .application import DisassemblyEditor


class XRefBrowser:
    def __init__(self, app: 'DisassemblyEditor'):
        self.asm = app.disassembler

        self.address: Optional[Address] = None
        self.index = 0

        self.refs_control = FormattedTextControl(
            self.get_xrefs_content,
            show_cursor=False,
            focusable=True,
            key_bindings=create_xref_inspect_bindings(app),
        )
        self.head_control = FormattedTextControl(self.get_header_content)

    def get_refs_count(self):
        xr = self.asm.xrefs.get_xrefs(self.address)
        return (
            len(xr.called_by) +
            len(xr.jumps_from) +
            len(xr.read_by) +
            len(xr.written_by)
        )

    def move_up(self):
        refs_count = self.get_refs_count()
        if refs_count:
            self.index -= 1
            self.index %= refs_count

    def move_down(self):
        refs_count = self.get_refs_count()
        if refs_count:
            self.index += 1
            self.index %= refs_count

    def get_xrefs_content(self):
        if self.address is None:
            return []

        xrefs = self.asm.xrefs.get_xrefs(self.address)
        calls = list(sorted(xrefs.called_by))
        jumps = list(sorted(xrefs.jumps_from))
        reads = list(sorted(xrefs.read_by))
        writes = list(sorted(xrefs.written_by))

        if not any([calls, jumps, reads, writes]):
            return [('', 'No references found')]

        nl = ('', '\n')
        line_index = 0
        tokens = []

        def get_name(_addr):
            return self.asm.context.address_context(
                _addr, _addr, ignore_scalar=True, allow_relative=True
            )

        def display_xref(_addr):
            tokens.append(('', '  '))
            sel = ',ugb.hl' * (line_index == self.index)
            tokens.append(('class:ugb.address' + sel, str(_addr)))

            name = get_name(_addr)
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

    def get_header_content(self):
        if self.address is None:
            return [('', 'No address selected')]

        tokens = [('', 'XREFs for: ')]
        address = ('', str(self.address))

        labels = self.asm.labels.get_labels(self.address)
        if labels:
            tokens.extend(
                [('', labels[-1].name), ('', ' ('), address, ('', ')')]
            )
        else:
            tokens.append(address)

        return tokens
