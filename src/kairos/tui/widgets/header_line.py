from __future__ import annotations

from rich.markup import escape
from textual.widgets import Static

from kairos.tui.state import TuiState

_GLYPH = "\u2b22"
_WELL_GLYPH = "\u25c8"
_OFFLINE_GLYPH = "\u25cf"


class HeaderLine(Static):
    def __init__(self) -> None:
        super().__init__(id="header-line")

    def refresh_from_state(self, state: TuiState) -> None:
        workspace_name = escape(state.workspace_path.name)
        well = escape(state.active_well) if state.active_well else "none"
        self.update(
            f" {_GLYPH} KAIROS  \u2502  ws: {workspace_name}  "
            f"\u2502  {_WELL_GLYPH} well: {well}  \u2502  {_OFFLINE_GLYPH} LOCAL"
        )
