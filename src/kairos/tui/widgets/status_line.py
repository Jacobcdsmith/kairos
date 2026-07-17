"""The bottom keybinding/status strip — always visible, never decorative-only:
it shows the current status message (including errors, in plain text, no
traceback) alongside the fixed keybinding legend.
"""

from __future__ import annotations

from rich.markup import escape
from textual.widgets import Static

from kairos.tui.state import TuiState

_LEGEND = (
    "↑↓ select · Enter inspect · Tab pane · / search · w wells · Ctrl+R history · ? help · q quit"
)


class StatusLine(Static):
    def __init__(self) -> None:
        super().__init__(_LEGEND, id="status-line")

    def refresh_from_state(self, state: TuiState) -> None:
        if state.status_message:
            message = escape(state.status_message)
            prefix = "[red]Error:[/red] " if state.status == "error" else "[dim]"
            suffix = "" if state.status == "error" else "[/dim]"
            self.update(f"{prefix}{message}{suffix}   —   {_LEGEND}")
        else:
            self.update(_LEGEND)
