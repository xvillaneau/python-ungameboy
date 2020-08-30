from functools import wraps
from typing import TYPE_CHECKING

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys

from .control import AsmControl

if TYPE_CHECKING:
    from .application import DisassemblyEditor


def load_layout_bindings(editor: "DisassemblyEditor"):
    prompt_active = Condition(lambda: editor.prompt_active)
    # editor_loaded = Condition(lambda: editor.disassembler.rom is not None)

    bindings = KeyBindings()

    @bindings.add("c-d")
    def _exit(event):
        event.app.exit()

    @bindings.add(":", filter=~prompt_active)
    def _focus_prompt(_):
        editor.layout.focus_prompt()

    @bindings.add("c-c", filter=prompt_active)
    @bindings.add(Keys.Escape, filter=prompt_active)
    def _quit_prompt(event):
        editor.layout.unfocus_prompt()
        editor.prompt.reset()

    return bindings


def load_asm_control_bindings(editor):
    bindings = KeyBindings()
    editor_active = ~Condition(lambda: editor.prompt_active)

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
            return bindings.add(*keys, filter=editor_active)(func)
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

    @bindings.add("pageup", filter=editor_active)
    def handle_page_up(event: KeyPressEvent):
        window = event.app.layout.current_window
        if not (window and window.render_info):
            return
        ctrl = window.content
        if isinstance(ctrl, AsmControl):
            ctrl.move_up(window.render_info.window_height)

    @bindings.add("pagedown", filter=editor_active)
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

    def _cursor_active():
        ctrl = get_app().layout.current_control
        return isinstance(ctrl, AsmControl) and ctrl.cursor_mode

    cursor_active = Condition(_cursor_active)
    editor_active = Condition(lambda: not editor.prompt_active)

    def bind_shortcut(keys, args, filter=None, run=False):
        if isinstance(keys, str):
            keys = (keys,)
        if isinstance(args, str):
            args = (args,)

        def handler(event: KeyPressEvent) -> None:
            ctrl = event.app.layout.current_control
            if not isinstance(ctrl, AsmControl):
                return
            str_args = (
                str(ctrl.cursor if arg is cursor else arg)
                for arg in args
            )
            if run:
                editor.prompt.run_command(*str_args)
            else:
                editor.prompt.pre_fill(*str_args)
                editor.layout.focus_prompt()

        bindings.add(*keys, filter=filter)(handler)

    bind_shortcut('g', 'seek', filter=editor_active)
    bind_shortcut(
        ('x', 'x'),
        ('xref', 'auto', cursor),
        run=True,
        filter=editor_active & cursor_active,
    )
