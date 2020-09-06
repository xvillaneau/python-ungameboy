from typing import TYPE_CHECKING

from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.keys import Keys

from .control import AsmControl

if TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyBindingsBase, KeyPressEvent
    from .application import DisassemblyEditor


def create_global_bindings(app: 'DisassemblyEditor') -> 'KeyBindingsBase':
    return merge_key_bindings([
        create_layout_bindings(app),
        create_editor_shortcuts(app),
    ])


def create_layout_bindings(editor: 'DisassemblyEditor'):
    bindings = KeyBindings()

    @bindings.add("c-d")
    def _exit(event):
        event.app.exit()

    @bindings.add(":", filter=~editor.filters.prompt_active)
    def _focus_prompt(_):
        editor.layout.focus_prompt()

    @bindings.add("c-c", filter=editor.filters.prompt_active)
    @bindings.add(Keys.Escape, filter=editor.filters.prompt_active)
    def _quit_prompt(_):
        editor.layout.unfocus_prompt()
        editor.prompt.reset()

    return bindings


def create_editor_shortcuts(editor: 'DisassemblyEditor'):
    bindings = KeyBindings()

    cursor = object()
    cursor_dest = object()

    def replace_arg(control: AsmControl, arg):
        if arg is cursor:
            return control.cursor
        if arg is cursor_dest:
            dest = control.cursor_destination
            if dest is None:
                raise ValueError()
            return dest
        return arg

    def bind_shortcut(keys, args, filter=None, run=False):
        if isinstance(keys, str):
            keys = (keys,)
        if isinstance(args, str):
            args = (args,)

        def handler(event: 'KeyPressEvent') -> None:
            ctrl = event.app.layout.current_control
            if not isinstance(ctrl, AsmControl):
                return

            try:
                str_args = [replace_arg(ctrl, arg) for arg in args]
            except ValueError:
                return

            if run:
                editor.prompt.run_command(*str_args)
            else:
                editor.prompt.pre_fill(*str_args)
                editor.layout.focus_prompt()

        bindings.add(*keys, filter=filter)(handler)

    bind_shortcut('g', 'seek', filter=editor.filters.editor_active)
    bind_shortcut(
        ('a', 'a'), ('label', 'auto', cursor), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        ('a', 'x'), ('label', 'auto', cursor_dest), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        ('A', 'a'), ('label', 'auto', cursor, '--local'), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        ('A', 'x'), ('label', 'auto', cursor_dest, '--local'), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        ('x', 'x'), ('xref', 'auto', cursor), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        ('x', 'r'), ('xref', 'declare', 'read', cursor),
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        ('x', 'w'), ('xref', 'declare', 'write', cursor),
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        ('C', 's'), ('context', 'force-scalar', cursor), run=True,
        filter=editor.filters.cursor_active,
    )

    return bindings


def create_xref_inspect_bindings(app: 'DisassemblyEditor'):
    bindings = KeyBindings()

    @bindings.add('up')
    def move_up(_):
        app.xrefs.move_up()

    @bindings.add('down')
    def move_down(_):
        app.xrefs.move_down()

    @bindings.add("c-c", filter=app.filters.xrefs_visible)
    @bindings.add('escape', filter=app.filters.xrefs_visible)
    def quit_inspector(event):
        app.xrefs.address = None

        control = event.app.layout.previous_control
        if not isinstance(control, AsmControl):
            control = app.layout.main_control
        event.app.layout.focus(control)

    return bindings


def create_asm_control_bindings(control: AsmControl):
    bindings = KeyBindings()

    @bindings.add("c")
    def toggle_cursor(_):
        control.toggle_cursor_mode()

    @bindings.add("u")
    def undo_seek(_):
        control.undo_seek()

    @bindings.add("U")
    def redo_seek(_):
        control.redo_seek()

    @bindings.add("enter")
    def follow_jump(_):
        control.follow_jump()

    @bindings.add("up")
    def handle_up(_):
        control.move_up(1)

    @bindings.add("down")
    def handle_down(_):
        control.move_down(1)

    @bindings.add("pageup")
    def handle_page_up(event: 'KeyPressEvent'):
        window = event.app.layout.current_window
        if not (window and window.render_info):
            return
        if window.content is control:
            control.move_up(window.render_info.window_height)

    @bindings.add("pagedown")
    def handle_page_down(event: 'KeyPressEvent'):
        window = event.app.layout.current_window
        if not (window and window.render_info):
            return
        if window.content is control:
            control.move_down(window.render_info.window_height)

    return bindings
