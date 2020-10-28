from functools import wraps
from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.keys import Keys

from .control import AsmControl
from .xref_browser import count_xrefs, get_selected_xref

if TYPE_CHECKING:
    from prompt_toolkit.key_binding import KeyBindingsBase, KeyPressEvent
    from .application import UGBApplication


def create_global_bindings(ugb: 'UGBApplication') -> 'KeyBindingsBase':
    return merge_key_bindings([
        create_layout_bindings(ugb),
        create_editor_shortcuts(ugb),
    ])


def create_layout_bindings(ugb: 'UGBApplication'):
    bindings = KeyBindings()

    @bindings.add("c-d")
    def _exit(event):
        event.app.exit()

    @bindings.add(":", filter=ugb.filters.browsing)
    def _focus_prompt(_):
        ugb.layout.focus_prompt()

    @bindings.add('tab', filter=ugb.filters.browsing)
    def _rotate_focus(event):
        event.app.layout.focus_next()

    @bindings.add("c-c", filter=ugb.filters.prompt_active)
    @bindings.add(Keys.Escape, filter=ugb.filters.prompt_active)
    def _quit_prompt(_):
        ugb.layout.exit_prompt()
        ugb.prompt.reset()

    return bindings


def create_editor_shortcuts(ugb: 'UGBApplication'):
    bindings = KeyBindings()

    cursor = object()
    cursor_dest = object()

    def replace_arg(control: AsmControl, arg):
        addr = control.address
        dest = control.destination_address

        if arg is cursor:
            return addr
        elif arg is cursor_dest:
            if dest is None:
                raise ValueError()
            return dest
        else:
            return arg

    def bind_shortcut(keys, args, filter=None, run=False):
        if isinstance(keys, str):
            keys = tuple(keys)
        if isinstance(args, str):
            args = (args,)

        def handler(event: 'KeyPressEvent') -> None:
            ctrl = event.app.layout.current_control
            if not isinstance(ctrl, AsmControl):
                return

            try:
                str_args = [str(replace_arg(ctrl, arg)) for arg in args]
            except ValueError:
                return

            if run:
                ugb.prompt.run_command(str_args)
            else:
                ugb.prompt.pre_fill(*str_args)
                ugb.layout.focus_prompt()

        bindings.add(*keys, filter=filter)(handler)

    # Navigation shortcuts
    bind_shortcut('g', 'seek', filter=ugb.filters.editor_active)
    bind_shortcut(
        'x', ('inspect', cursor), run=True,
        filter=ugb.filters.cursor_active,
    )
    bind_shortcut(
        'X', ('inspect', cursor_dest), run=True,
        filter=ugb.filters.cursor_active,
    )
    bind_shortcut(
        'V', ('display', cursor), run=True,
        filter=ugb.filters.cursor_active,
    )
    bind_shortcut(
        ('c-s',), ('project', 'save'), run=True,
        filter=~ugb.filters.prompt_active,
    )

    # Label shortcuts
    bind_shortcut(
        'aa', ('label', 'auto', cursor), run=True,
        filter=ugb.filters.cursor_active,
    )
    bind_shortcut(
        'ax', ('label', 'auto', cursor_dest), run=True,
        filter=ugb.filters.cursor_active,
    )
    bind_shortcut(
        'Aa', ('label', 'auto', cursor, '--local'), run=True,
        filter=ugb.filters.cursor_active,
    )
    bind_shortcut(
        'Ax', ('label', 'auto', cursor_dest, '--local'), run=True,
        filter=ugb.filters.cursor_active,
    )

    # Context shortcuts
    bind_shortcut(
        'Cs', ('context', 'set', 'scalar', cursor), run=True,
        filter=ugb.filters.cursor_active,
    )
    bind_shortcut(
        'Cb', ('context', 'set', 'bank', cursor),
        filter=ugb.filters.cursor_active,
    )
    return bindings


def quit_sidebar(ugb: 'UGBApplication'):
    def decorator(func):
        @wraps(func)
        def wrapper(event):
            func(event)

            control = event.app.layout.previous_control
            if not isinstance(control, AsmControl):
                control = ugb.layout.main_control
            event.app.layout.focus(control)
        return wrapper
    return decorator


def create_xref_inspect_bindings(ugb: 'UGBApplication'):
    bindings = KeyBindings()

    @bindings.add('up')
    def move_up(_):
        ugb.xrefs.cursor = max(ugb.xrefs.cursor - 1, 0)

    @bindings.add('down')
    def move_down(_):
        ugb.xrefs.cursor = min(ugb.xrefs.cursor + 1, count_xrefs(ugb) - 1)

    @bindings.add('enter')
    def go_to_ref(event):
        show_ref(event)
        event.app.layout.focus(ugb.layout.main_control)

    @bindings.add('space')
    def show_ref(_):
        ugb.layout.main_control.seek(get_selected_xref(ugb))

    @bindings.add("q")
    @bindings.add("c-c")
    @quit_sidebar(ugb)
    def quit_inspector(_):
        ugb.xrefs.address = None

    return bindings


def create_gfx_display_bindings(ugb: 'UGBApplication'):
    bindings = KeyBindings()

    @bindings.add("q")
    @bindings.add("c-c")
    @quit_sidebar(ugb)
    def quit_display(_):
        ugb.gfx.address = None

    @bindings.add('[')
    def more_columns(_):
        ugb.gfx.columns += 1

    @bindings.add(']')
    def fewer_columns(_):
        ugb.gfx.columns = max(1, ugb.gfx.columns - 1)

    @bindings.add('p')
    def toggle_tall_sprites(_):
        # Toggle between 8 and 16
        ugb.gfx.tile_height = 8 * (3 - ugb.gfx.tile_height // 8)

    @bindings.add('n')
    def show_ids(_):
        ugb.gfx.show_ids = not ugb.gfx.show_ids

    @bindings.add("down")
    def move_down(_):
        ugb.layout.gfx_control.move_down(1)

    @bindings.add("up")
    def move_up(_):
        ugb.layout.gfx_control.move_up(1)

    @bindings.add("pageup")
    def handle_page_up(event: 'KeyPressEvent'):
        window = event.app.layout.current_window
        if not (window and window.render_info):
            return
        control = ugb.layout.gfx_control
        if window.content is control:
            control.move_up(window.render_info.window_height // 2)

    @bindings.add("pagedown")
    def handle_page_down(event: 'KeyPressEvent'):
        window = event.app.layout.current_window
        if not (window and window.render_info):
            return
        control = ugb.layout.gfx_control
        if window.content is control:
            control.move_down(window.render_info.window_height // 2)

    return bindings


def create_asm_control_bindings(control: AsmControl):
    bindings = KeyBindings()

    commenting = Condition(lambda: control.comment_mode)
    cursor_mode = Condition(lambda: control.cursor_mode)

    # Movement bindings, always active

    @bindings.add("up")
    def handle_up(_):
        control.move_up(1)

    @bindings.add("down")
    def handle_down(_):
        control.move_down(1)

    @bindings.add("left")
    def handle_left(_):
        control.move_left(1)

    @bindings.add("right")
    def handle_right(_):
        control.move_right(1)

    @bindings.add("home")
    def handle_home(_):
        control.move_home()

    @bindings.add("end")
    def handle_end(_):
        control.move_end()

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

    # Browsing mode bindings

    @bindings.add("c", filter=~commenting)
    def toggle_cursor(_):
        control.toggle_cursor_mode()

    @bindings.add("u", filter=~commenting)
    def undo_seek(_):
        control.undo_seek()

    @bindings.add("U", filter=~commenting)
    def redo_seek(_):
        control.redo_seek()

    @bindings.add("enter", filter=~commenting)
    def follow_jump(_):
        control.follow_jump()

    @bindings.add(';', filter=~commenting)
    def enter_comment(_):
        control.enter_comment_mode()

    # Commenting bindings

    @bindings.add('escape', filter=commenting)
    @bindings.add('enter', filter=commenting)
    @bindings.add('c-c', filter=commenting)
    def handle_quit_comment(_):
        control.exit_comment_mode()

    @bindings.add('delete', filter=commenting)
    def handle_delete(event: 'KeyPressEvent'):
        control.delete_after(event.arg)

    @bindings.add('backspace', filter=commenting)
    def handle_backspace(event: 'KeyPressEvent'):
        if event.arg < 0:
            control.delete_after(-event.arg)
        else:
            control.delete_before(event.arg)

    @bindings.add('c-up', filter=commenting | cursor_mode)
    @bindings.add('c-left', filter=commenting | cursor_mode)
    def handle_add_line_above(_):
        if not control.comment_mode:
            control.enter_comment_mode()
        control.add_line_above()

    @bindings.add('c-down', filter=commenting | cursor_mode)
    @bindings.add('c-right', filter=commenting | cursor_mode)
    def handle_add_line_below(_):
        if not control.comment_mode:
            control.enter_comment_mode()
        control.add_line_below()

    @bindings.add('c-x', filter=commenting)
    @bindings.add('c-delete', filter=commenting)
    def handle_delete_line(_):
        control.delete_line()

    @bindings.add('<any>', filter=commenting)
    def handle_insert(event: 'KeyPressEvent'):
        control.insert_str(event.data * event.arg)

    return bindings
