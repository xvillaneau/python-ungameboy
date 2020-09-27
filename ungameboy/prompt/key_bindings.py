from functools import wraps
from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings, merge_key_bindings
from prompt_toolkit.keys import Keys

from .control import AsmControl
from ..address import ROM

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

    @bindings.add(":", filter=editor.filters.browsing)
    def _focus_prompt(_):
        editor.layout.focus_prompt()

    @bindings.add('tab', filter=editor.filters.browsing)
    def _rotate_focus(event):
        event.app.layout.focus_next()

    @bindings.add("c-c", filter=editor.filters.prompt_active)
    @bindings.add(Keys.Escape, filter=editor.filters.prompt_active)
    def _quit_prompt(_):
        editor.layout.exit_prompt()
        editor.prompt.reset()

    return bindings


def create_editor_shortcuts(editor: 'DisassemblyEditor'):
    bindings = KeyBindings()

    cursor = object()
    cursor_dest = object()
    cursor_dest_rom = object()

    def replace_arg(control: AsmControl, arg):
        addr = control.address
        dest = control.destination_address

        use_addr = arg is cursor
        use_dest = arg is cursor_dest
        if arg is cursor_dest_rom:
            use_dest = addr.type is ROM
            use_addr = not use_dest

        if use_addr:
            return addr
        if use_dest:
            if dest is None:
                raise ValueError()
            return dest

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
                editor.prompt.run_command(str_args)
            else:
                editor.prompt.pre_fill(*str_args)
                editor.layout.focus_prompt()

        bindings.add(*keys, filter=filter)(handler)

    # Navigation shortcuts
    bind_shortcut('g', 'seek', filter=editor.filters.editor_active)
    bind_shortcut(
        'X', ('inspect', cursor_dest_rom), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        'V', ('display', cursor), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        ('c-s',), ('project', 'save'), run=True,
        filter=~editor.filters.prompt_active,
    )

    # Label shortcuts
    bind_shortcut(
        'aa', ('label', 'auto', cursor), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        'ax', ('label', 'auto', cursor_dest), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        'Aa', ('label', 'auto', cursor, '--local'), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        'Ax', ('label', 'auto', cursor_dest, '--local'), run=True,
        filter=editor.filters.cursor_active,
    )

    # XREF shortcuts
    bind_shortcut(
        'xx', ('xref', 'auto', cursor), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        'xr', ('xref', 'declare', 'read', cursor),
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        'xw', ('xref', 'declare', 'write', cursor),
        filter=editor.filters.cursor_active,
    )

    # Context shortcuts
    bind_shortcut(
        'Cs', ('context', 'set', 'scalar', cursor), run=True,
        filter=editor.filters.cursor_active,
    )
    bind_shortcut(
        'Cb', ('context', 'set', 'bank', cursor),
        filter=editor.filters.cursor_active,
    )
    return bindings


def quit_sidebar(app: 'DisassemblyEditor'):
    def decorator(func):
        @wraps(func)
        def wrapper(event):
            func(event)

            control = event.app.layout.previous_control
            if not isinstance(control, AsmControl):
                control = app.layout.main_control
            event.app.layout.focus(control)
        return wrapper
    return decorator


def create_xref_inspect_bindings(app: 'DisassemblyEditor'):
    bindings = KeyBindings()

    def count_refs():
        xr = app.disassembler.xrefs.get_xrefs(app.xrefs.address)
        return (
            len(xr.called_by) +
            len(xr.jumps_from) +
            len(xr.read_by) +
            len(xr.written_by)
        )

    def get_selected_xref():
        index = app.xrefs.cursor
        if index < 0:
            raise IndexError(index)

        xr = app.disassembler.xrefs.get_xrefs(app.xrefs.address)
        for col in (xr.called_by, xr.jumps_from, xr.read_by, xr.written_by):
            if index < len(col):
                return list(sorted(col))[index]
            index -= len(col)

        raise IndexError(app.xrefs.cursor)

    @bindings.add('up')
    def move_up(_):
        app.xrefs.cursor = max(app.xrefs.cursor - 1, 0)

    @bindings.add('down')
    def move_down(_):
        app.xrefs.cursor = min(app.xrefs.cursor + 1, count_refs() - 1)

    @bindings.add('enter')
    def go_to_ref(event):
        show_ref(event)
        event.app.layout.focus(app.layout.main_control)

    @bindings.add('space')
    def show_ref(_):
        app.layout.main_control.seek(get_selected_xref())

    @bindings.add("q")
    @bindings.add("c-c")
    @quit_sidebar(app)
    def quit_inspector(_):
        app.xrefs.address = None

    return bindings


def create_gfx_display_bindings(app: 'DisassemblyEditor'):
    bindings = KeyBindings()

    @bindings.add("q")
    @bindings.add("c-c")
    @quit_sidebar(app)
    def quit_display(_):
        app.gfx.address = None

    @bindings.add('[')
    def more_columns(_):
        app.gfx.columns += 1

    @bindings.add(']')
    def fewer_columns(_):
        app.gfx.columns = max(1, app.gfx.columns - 1)

    @bindings.add('p')
    def toggle_tall_sprites(_):
        # Toggle between 8 and 16
        app.gfx.tile_height = 8 * (3 - app.gfx.tile_height // 8)

    @bindings.add('n')
    def show_ids(_):
        app.gfx.show_ids = not app.gfx.show_ids

    @bindings.add("down")
    def move_down(_):
        app.layout.gfx_control.move_down(1)

    @bindings.add("up")
    def move_up(_):
        app.layout.gfx_control.move_up(1)

    @bindings.add("pageup")
    def handle_page_up(event: 'KeyPressEvent'):
        window = event.app.layout.current_window
        if not (window and window.render_info):
            return
        control = app.layout.gfx_control
        if window.content is control:
            control.move_up(window.render_info.window_height // 2)

    @bindings.add("pagedown")
    def handle_page_down(event: 'KeyPressEvent'):
        window = event.app.layout.current_window
        if not (window and window.render_info):
            return
        control = app.layout.gfx_control
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
