from typing import TYPE_CHECKING

from prompt_toolkit.filters import Condition

from .control import AsmControl

if TYPE_CHECKING:
    from .application import DisassemblyEditor


class UGBFilters:
    def __init__(self, app: 'DisassemblyEditor'):
        self.app = app

        self.prompt_active = Condition(self._prompt_active)
        self.xrefs_visible = Condition(self._xrefs_visible)
        self.gfx_visible = Condition(self._gfx_visible)
        self.editor_active = Condition(self._editor_active)
        self.cursor_active = Condition(self._cursor_active)
        self.commenting = Condition(self._comment_mode_active)

        self.browsing = ~(self.prompt_active | self.commenting)

    def _editor_active(self):
        ctrl = self.app.layout.layout.current_control
        return isinstance(ctrl, AsmControl) and not ctrl.comment_mode

    def _comment_mode_active(self):
        ctrl = self.app.layout.layout.current_control
        return isinstance(ctrl, AsmControl) and ctrl.comment_mode

    def _cursor_active(self):
        ctrl = self.app.layout.layout.current_control
        return isinstance(ctrl, AsmControl) and ctrl.cursor_mode

    def _prompt_active(self):
        return self.app.prompt_active

    def _xrefs_visible(self):
        return self.app.xrefs.address is not None

    def _gfx_visible(self):
        return self.app.gfx.address is not None
