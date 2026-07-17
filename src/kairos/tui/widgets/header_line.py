"""The top bar: workspace name, active coherence well (the TUI's visible
context boundary — see docs/tli-implementation-plan.md), and a constant
LOCAL / OFFLINE marker. Not Textual's built-in ``Header`` (that renders a
clock/title bar Textual owns); this is a plain ``Static`` under our control.
"""

from __future__ import annotations

from rich.markup import escape
from textual.widgets import Static

from kairos.tui.state import TuiState


class HeaderLine(Static):
    def __init__(self) -> None:
        super().__init__(id="header-line")

    def refresh_from_state(self, state: TuiState) -> None:
        workspace_name = escape(state.workspace_path.name)
        well = escape(state.active_well) if state.active_well else "none"
        self.update(f"KAIROS — workspace: {workspace_name} — well: {well} — LOCAL / OFFLINE")
