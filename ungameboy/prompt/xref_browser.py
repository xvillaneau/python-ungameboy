from typing import TYPE_CHECKING, Optional, Set

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

    def get_refs_count(self):
        xr = self.asm.xrefs.get_xrefs(self.address)
        return (
            len(xr.called_by) +
            len(xr.jumps_from) +
            len(xr.read_by) +
            len(xr.written_by)
        )

    def move_up(self):
        self.index = max(self.index - 1, 0)

    def move_down(self):
        refs_count = self.get_refs_count()
        self.index = min(self.index + 1, refs_count - 1)

    def get_selected_xref(self) -> Address:
        index = self.index
        if index < 0:
            raise IndexError(index)

        xr = self.asm.xrefs.get_xrefs(self.address)

        def _get_index(collection: Set[Address]):
            nonlocal index
            if index < len(collection):
                return list(sorted(collection))[index]
            else:
                index -= len(collection)
                return None

        for col in (xr.called_by, xr.jumps_from, xr.read_by, xr.written_by):
            res = _get_index(col)
            if res is not None:
                return res

        raise IndexError(self.index)

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

        def display_xref(_addr):
            tokens.append(('', '  '))
            sel = ',ugb.hl' * (line_index == self.index)
            tokens.append(('class:ugb.address' + sel, str(_addr)))

            name = self.asm.context.address_context(_addr, _addr, relative=True)
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

    def get_header_text(self):
        if self.address is None:
            return 'No address selected'

        labels = self.asm.labels.get_labels(self.address)
        if labels:
            target = f'{labels[-1].name} ({self.address})'
        else:
            target = str(self.address)

        return f'XREFs for: {target}'
