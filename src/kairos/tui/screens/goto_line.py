"""Explorer's "go to item" prompt (Ctrl+G): jump straight to row N without
scrolling through a long result set by hand.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, Static


class GotoLineScreen(ModalScreen[int | None]):
    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(self, max_index: int) -> None:
        super().__init__()
        self._max_index = max_index

    def compose(self) -> ComposeResult:
        with Vertical(id="goto-line-container"):
            yield Static(f"Go to item # (1–{self._max_index}), Escape to cancel")
            yield Input(placeholder="item number", id="goto-line-input")

    def on_mount(self) -> None:
        self.query_one("#goto-line-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        if text.isdigit() and 1 <= int(text) <= self._max_index:
            self.dismiss(int(text))
        else:
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)
