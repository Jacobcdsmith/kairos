"""Tab bar showing the current mode/view. Visual indicator of where you are."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from kairos.tui.state import TuiState

_MODE_LABELS = {
    "home": "\u25cb Home",
    "artifacts": "\u25a1 Artifacts",
    "search": "\u25cf Search",
    "show": "\u25a1 Detail",
    "trace": "\u25c6 Trace",
    "well": "\u25c8 Wells",
    "config": "\u2699 Config",
    "logs": "\u2261 Logs",
    "doctor": "\u2699 Doctor",
    "history": "\u25b8 History",
    "help": "? Help",
    "notes": "\u270e Notes",
    "bookmarks": "\u2605 Bookmarks",
}

_BOOKMARK_GLYPH = "\u2605"


class _TabItem(Static):
    def __init__(
        self, label: str, mode: str, active: bool = False, classes: str = "tab-item"
    ) -> None:
        super().__init__(label, classes=f"{classes} active" if active else classes)
        self.mode = mode


class TabBar(Horizontal):
    def __init__(self) -> None:
        super().__init__(id="tab-bar")

    def compose(self) -> ComposeResult:
        yield _TabItem("\u25cb Home", "home", active=True)

    def refresh_from_state(self, state: TuiState) -> None:
        self.remove_children()
        label = _MODE_LABELS.get(state.mode, state.mode)
        self.mount(_TabItem(label, state.mode, active=True))
        # Most-recently-saved first, matching the bookmark picker's ordering.
        for bookmark in reversed(state.recent_bookmarks):
            self.mount(
                _TabItem(
                    f"{_BOOKMARK_GLYPH} {bookmark.name}",
                    "bookmarks",
                    classes="tab-item bookmark",
                )
            )
