"""Fuzzy finder overlay: quick navigation across all navigable items.
Ctrl+P opens it, type to filter, Enter to select and navigate.
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Input, ListItem, ListView, Static

from kairos.services.artifacts import list_artifacts
from kairos.services.context import RuntimeContext


@dataclass(frozen=True, slots=True)
class FinderItem:
    label: str
    sublabel: str
    kind: str
    target_id: str


class _FinderListItem(ListItem):
    def __init__(self, item: FinderItem) -> None:
        text = escape(item.label)
        if item.sublabel:
            text += f"\n[dim]{escape(item.sublabel)}[/dim]"
        super().__init__(Static(text))
        self.finder_item = item


class FuzzyFinderScreen(ModalScreen[FinderItem | None]):
    BINDINGS = [("escape", "cancel", "Close")]

    def __init__(self, runtime_ctx: RuntimeContext) -> None:
        super().__init__()
        self._runtime_ctx = runtime_ctx
        self._all_items: list[FinderItem] = []

    def compose(self) -> ComposeResult:
        with Vertical(id="fuzzy-container"):
            yield Input(placeholder="Type to filter...", id="fuzzy-input")
            yield ListView(id="fuzzy-list")

    def on_mount(self) -> None:
        artifacts = list_artifacts(self._runtime_ctx)
        self._all_items = [
            FinderItem(
                label=f"[{a.kind}] {a.source_path}",
                sublabel=f"{a.parse_status} \u00b7 {a.size_bytes}B",
                kind="artifact",
                target_id=a.id,
            )
            for a in artifacts
        ]
        self._refresh_list("")
        self.query_one("#fuzzy-input", Input).focus()

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "fuzzy-input":
            self._refresh_list(event.value)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        list_view = self.query_one("#fuzzy-list", ListView)
        if list_view.highlighted_child is not None:
            item = list_view.highlighted_child
            if isinstance(item, _FinderListItem):
                self.dismiss(item.finder_item)
        else:
            self.dismiss(None)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, _FinderListItem):
            self.dismiss(item.finder_item)

    def _refresh_list(self, query: str) -> None:
        list_view = self.query_one("#fuzzy-list", ListView)
        list_view.clear()

        if not query:
            filtered = self._all_items
        else:
            query_lower = query.lower()
            filtered = [
                item
                for item in self._all_items
                if query_lower in item.label.lower() or query_lower in item.sublabel.lower()
            ]

        for item in filtered[:50]:
            list_view.append(_FinderListItem(item))

        if filtered:
            list_view.index = 0

    def action_cancel(self) -> None:
        self.dismiss(None)
