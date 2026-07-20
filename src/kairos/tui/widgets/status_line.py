from __future__ import annotations

from rich.markup import escape
from textual.widgets import Static

from kairos.tui.state import TuiState

_ARROW = "\u203a"
_SEP = "\u2502"
_LEGEND = (
    f" {_ARROW} select  {_SEP} Enter inspect  {_SEP} Tab pane  "
    f"{_SEP} / search  {_SEP} w wells  {_SEP} ^P find"
    f"  {_SEP} t tutorial  {_SEP} ? help  {_SEP} q quit"
)


class StatusLine(Static):
    def __init__(self) -> None:
        super().__init__(_LEGEND, id="status-line")

    def refresh_from_state(self, state: TuiState) -> None:
        if state.status_message:
            message = escape(state.status_message)
            if state.status == "error":
                prefix = "[red]\u2717[/red] "
                self.update(f"{prefix}{message}   {_SEP}{_LEGEND}")
            else:
                prefix = "[dim]\u2713[/dim] "
                self.update(f"{prefix}[dim]{message}[/dim]   {_SEP}{_LEGEND}")
        else:
            self.update(_LEGEND)
