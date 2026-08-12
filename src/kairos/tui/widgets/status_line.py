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

    def show_running(self, command_text: str) -> None:
        """Transient yellow "still running" indicator, shown the instant a
        command is dispatched \u2014 before its worker thread has returned \u2014
        and overwritten by the next ``refresh_from_state`` once it does.
        """
        message = escape(command_text.strip())
        self.update(f"[yellow]\u25cc running: {message}...[/yellow]   {_SEP}{_LEGEND}")

    def refresh_from_state(self, state: TuiState) -> None:
        if state.status_message:
            message = escape(state.status_message)
            if state.status == "error":
                prefix = "[red]\u2717[/red] "
                self.update(f"{prefix}[red]{message}[/red]   {_SEP}{_LEGEND}")
            else:
                prefix = "[green]\u2713[/green] "
                self.update(f"{prefix}[green]{message}[/green]   {_SEP}{_LEGEND}")
        else:
            self.update(_LEGEND)
