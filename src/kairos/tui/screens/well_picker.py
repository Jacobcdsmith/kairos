"""The coherence-well selector overlay: activate or clear the active well.
It only ever reads (``list_all_wells``) — it cannot create a well or add/
remove a member; those stay CLI-only in this alpha (see
docs/tli-implementation-plan.md's read-only-enforcement section).
"""

from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import ListItem, ListView, Static

from kairos.schemas.well import WellSummary
from kairos.services.context import RuntimeContext
from kairos.services.wells import list_all_wells

WellPickerResult = tuple[str, str | None]  # ("use", name) | ("clear", None) | ("cancel", None)


class _WellItem(ListItem):
    def __init__(self, summary: WellSummary) -> None:
        text = (
            f"{escape(summary.name)}\n"
            f"[dim]{escape(summary.purpose)} · {summary.member_count} member(s) · "
            f"created {summary.created_at.isoformat(timespec='seconds')}[/dim]"
        )
        super().__init__(Static(text))
        self.well_name = summary.name


class WellPickerScreen(ModalScreen[WellPickerResult]):
    BINDINGS = [
        ("escape", "cancel", "Close"),
        ("c", "clear_well", "Clear active well"),
    ]

    def __init__(self, runtime_ctx: RuntimeContext) -> None:
        super().__init__()
        self._runtime_ctx = runtime_ctx

    def compose(self) -> ComposeResult:
        with Vertical(id="well-picker-container"):
            yield Static("Coherence wells — Enter activates, c clears, Escape closes")
            yield ListView(id="well-picker-list")

    def on_mount(self) -> None:
        list_view = self.query_one("#well-picker-list", ListView)
        summaries = list_all_wells(self._runtime_ctx)
        for summary in summaries:
            list_view.append(_WellItem(summary))
        if summaries:
            list_view.index = 0
        list_view.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, _WellItem):
            self.dismiss(("use", item.well_name))

    def action_clear_well(self) -> None:
        self.dismiss(("clear", None))

    def action_cancel(self) -> None:
        self.dismiss(("cancel", None))
