from functools import wraps
from typing import TYPE_CHECKING

from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys

from .control import AsmControl

if TYPE_CHECKING:
    from .application import DisassemblyEditor


def load_layout_bindings(editor: "DisassemblyEditor"):

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

    @bindings.add("c-c", filter=editor.filters.prompt_active)
    @bindings.add(Keys.Escape, filter=editor.filters.prompt_active)
    def _quit_prompt(_):
        editor.layout.unfocus_prompt()
        editor.prompt.reset()

    @bindings.add("c-c", filter=editor.filters.xrefs_visible)
    @bindings.add(Keys.Escape, filter=editor.filters.xrefs_visible)
    def _quit_inspector(event):
        editor.xrefs_address = None
        event.app.layout.focus(editor.layout.main_control)

    return bindings


def load_asm_control_bindings(editor: 'DisassemblyEditor'):
    bindings = KeyBindings()

    def handle_active_asm(func):
        @wraps(func)
        def handler(event: KeyPressEvent) -> None:
            ctrl = event.app.layout.current_control
            if isinstance(ctrl, AsmControl):
                func(ctrl)
        return handler

    def asm_control_binding(*keys):
        def decorator(func):
            func = handle_active_asm(func)
            return bindings.add(
                *keys, filter=editor.filters.editor_active
            )(func)
        return decorator

    @asm_control_binding("c")
    def toggle_cursor(ctrl: AsmControl):
        ctrl.toggle_cursor_mode()

    @asm_control_binding("u")
    def undo_seek(ctrl: AsmControl):
        ctrl.undo_seek()

    @asm_control_binding("U")
    def redo_seek(ctrl: AsmControl):
        ctrl.redo_seek()

    @asm_control_binding("enter")
    def follow_jump(ctrl: AsmControl):
        ctrl.follow_jump()

    @asm_control_binding("up")
    def handle_up(ctrl: AsmControl):
        ctrl.move_up(1)

    @asm_control_binding("down")
    def handle_down(ctrl: AsmControl):
        ctrl.move_down(1)

    @bindings.add("pageup", filter=editor.filters.editor_active)
    def handle_page_up(event: KeyPressEvent):
        window = event.app.layout.current_window
        if not (window and window.render_info):
            return
        ctrl = window.content
        if isinstance(ctrl, AsmControl):
            ctrl.move_up(window.render_info.window_height)

    @bindings.add("pagedown", filter=editor.filters.editor_active)
    def handle_page_down(event: KeyPressEvent):
        window = event.app.layout.current_window
        if not (window and window.render_info):
            return
        ctrl = window.content
        if isinstance(ctrl, AsmControl):
            ctrl.move_down(window.render_info.window_height)

    add_editor_shortcuts(editor, bindings)

    return bindings


def add_editor_shortcuts(editor: "DisassemblyEditor", bindings: KeyBindings):

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

        def handler(event: KeyPressEvent) -> None:
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
        filter=editor.filters.shortcuts_active,
    )
    bind_shortcut(
        ('a', 'x'), ('label', 'auto', cursor_dest), run=True,
        filter=editor.filters.shortcuts_active,
    )
    bind_shortcut(
        ('A', 'a'), ('label', 'auto', cursor, '--local'), run=True,
        filter=editor.filters.shortcuts_active,
    )
    bind_shortcut(
        ('A', 'x'), ('label', 'auto', cursor_dest, '--local'), run=True,
        filter=editor.filters.shortcuts_active,
    )
    bind_shortcut(
        ('x', 'x'), ('xref', 'auto', cursor), run=True,
        filter=editor.filters.shortcuts_active,
    )
    bind_shortcut(
        ('x', 'r'), ('xref', 'declare', 'read', cursor),
        filter=editor.filters.shortcuts_active,
    )
    bind_shortcut(
        ('x', 'w'), ('xref', 'declare', 'write', cursor),
        filter=editor.filters.shortcuts_active,
    )

    bind_shortcut(
        ('C', 's'), ('context', 'force-scalar', cursor), run=True,
        filter=editor.filters.shortcuts_active,
    )
