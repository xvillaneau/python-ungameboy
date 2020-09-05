from typing import TYPE_CHECKING

from prompt_toolkit.layout.containers import (
    ConditionalContainer, HSplit, VSplit, Window
)
from prompt_toolkit.layout.controls import FormattedTextControl

from ..dis import Label, LabelOffset

if TYPE_CHECKING:
    from .application import DisassemblyEditor


def build_xref_sidebar(app: 'DisassemblyEditor'):

    def get_header_content():

        tokens = [('', 'XREFs for: ')]
        address = ('', str(app.xrefs_address))

        labels = app.disassembler.labels.get_labels(app.xrefs_address)
        if labels:
            tokens.extend(
                [('', labels[-1].name), ('', ' ('), address, ('', ')')]
            )
        else:
            tokens.append(address)

        return tokens

    header = Window(
        content=FormattedTextControl(get_header_content),
        dont_extend_height=True,
    )

    def get_xrefs_content():

        xrefs = app.disassembler.xrefs.get_xrefs(app.xrefs_address)
        calls = list(sorted(xrefs.called_by))
        jumps = list(sorted(xrefs.jumps_from))
        reads = list(sorted(xrefs.read_by))
        writes = list(sorted(xrefs.written_by))

        opt_count = sum(map(len, [calls, jumps, reads, writes]))
        if not opt_count:
            return [('', 'No references')]

        app.xrefs_cursor_index %= opt_count

        nl = ('', '\n')
        line_index = 0
        tokens = []

        def get_name(_addr):
            return app.disassembler.context.address_context(
                _addr, _addr, ignore_scalar=True, allow_relative=True
            )

        def display_xref(_addr):
            # sel = 'class:ugb.hl' * (line_index == app.xrefs_cursor_index)
            tokens.extend([('', '  '), ('class:ugb.address', str(_addr))])

            label = get_name(_addr)
            if isinstance(label, Label):
                tokens.extend(
                    [
                        ('', ' ('),
                        ('class:ugb.value.label', label.name),
                        ('', ')'),
                    ]
                )
            elif isinstance(label, LabelOffset):
                offset = f"{'-' if label.offset < 0 else '+'}${label.offset:x}"
                tokens.extend(
                    [
                        ('', ' ('),
                        ('class:ugb.value.label', label.label.name),
                        ('', ' '),
                        ('class:ugb.value', offset),
                        ('', ')'),
                    ]
                )

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

    xrefs_window = Window(
        content=FormattedTextControl(get_xrefs_content, show_cursor=False)
    )
    sep = Window(height=1, char='\u2500')

    xrefs_stack = HSplit([header, sep, xrefs_window])

    return xrefs_window, ConditionalContainer(
        content=VSplit([Window(width=1, char='\u2502'), xrefs_stack]),
        filter=app.filters.xrefs_visible,
    )
