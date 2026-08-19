"""Bookmark quick-access overlay (Shift+B): pick a saved bookmark and
re-run its command. Mostly read-only like the well picker, but ``d``
removes a bookmark on the spot — deleting a saved shortcut isn't source
mutation, unlike wells' create/add-member restriction, so there's no reason
to push it out to the CLI-only surface.
"""

from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, Static

from kairos.schemas.bookmark import BookmarkResult
from kairos.services.bookmarks import list_bookmarks, remove_bookmark
from kairos.services.context import RuntimeContext


class _BookmarkItem(ListItem):
    def __init__(self, bookmark: BookmarkResult) -> None:
        text = (
            f"{escape(bookmark.name)}\n"
            f"[dim]{escape(bookmark.command)} · "
            f"saved {bookmark.created_at.isoformat(timespec='seconds')}[/dim]"
        )
        super().__init__(Static(text))
        self.bookmark = bookmark


class BookmarkPickerScreen(ModalScreen[str | None]):
    """Dismisses with the chosen bookmark's command string, or ``None``."""

    BINDINGS = [
        ("escape", "cancel", "Close"),
        ("d", "remove_selected", "Remove bookmark"),
    ]

    def __init__(self, runtime_ctx: RuntimeContext) -> None:
        super().__init__()
        self._runtime_ctx = runtime_ctx

    def compose(self) -> ComposeResult:
        with Vertical(id="bookmark-picker-container"):
            yield Static("Bookmarks — Enter runs, d removes, Escape closes")
            yield ListView(id="bookmark-picker-list")

    def on_mount(self) -> None:
        self._refresh_list()

    def _refresh_list(self) -> None:
        list_view = self.query_one("#bookmark-picker-list", ListView)
        list_view.clear()
        # Most-recently-saved first — matches what the tab bar highlights.
        bookmarks = list(reversed(list_bookmarks(self._runtime_ctx)))
        for bookmark in bookmarks:
            list_view.append(_BookmarkItem(bookmark))
        if bookmarks:
            list_view.index = 0
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, _BookmarkItem):
            self.dismiss(item.bookmark.command)

    def action_remove_selected(self) -> None:
        list_view = self.query_one("#bookmark-picker-list", ListView)
        item = list_view.highlighted_child
        if isinstance(item, _BookmarkItem):
            remove_bookmark(self._runtime_ctx, item.bookmark.name)
            self._refresh_list()

    def action_cancel(self) -> None:
        self.dismiss(None)
