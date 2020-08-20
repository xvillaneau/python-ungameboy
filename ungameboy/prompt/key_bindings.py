from functools import wraps

from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, KeyPressEvent
from prompt_toolkit.keys import Keys

from .control import AsmControl


def load_layout_bindings(editor):
    prompt_active = Condition(lambda: editor.prompt_active)
    # editor_loaded = Condition(lambda: editor.disassembler.rom is not None)

    bindings = KeyBindings()

    @bindings.add("c-d")
    def _exit(event):
        event.app.exit()

    @bindings.add(":", filter=~prompt_active)
    def _focus_prompt(event):
        editor.prompt_active = True
        event.app.layout.focus(editor.prompt.container)

    @bindings.add("c-c", filter=prompt_active)
    @bindings.add(Keys.Escape, filter=prompt_active)
    def _quit_prompt(event):
        editor.prompt_active = False
        editor.prompt.reset()
        event.app.layout.focus_last()

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

    def asm_control_binding(key):
        def decorator(func):
            func = handle_active_asm(func)
            return bindings.add(key, filter=editor_active)(func)
        return decorator

    @asm_control_binding("up")
    def handle_up(ctrl: AsmControl):
        ctrl.move_up(1)

    @asm_control_binding("down")
    def handle_down(ctrl: AsmControl):
        ctrl.move_down(1)

    @asm_control_binding("pageup")
    def handle_page_up(ctrl: AsmControl):
        ctrl.move_up(ctrl.height)

    @asm_control_binding("pagedown")
    def handle_page_down(ctrl: AsmControl):
        ctrl.move_down(ctrl.height)

    return bindings
