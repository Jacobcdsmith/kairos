"""The main screen: header, three-pane workspace, command line, status line.
Responsive to terminal width via ``KairosApp.layout_mode`` — see
docs/tli-implementation-plan.md's Layouts section.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Static

from kairos.tui.state import TuiState
from kairos.tui.widgets.command_line import CommandLine
from kairos.tui.widgets.evidence_pane import EvidencePane
from kairos.tui.widgets.explorer_pane import ExplorerPane
from kairos.tui.widgets.header_line import HeaderLine
from kairos.tui.widgets.status_line import StatusLine
from kairos.tui.widgets.workspace_pane import WorkspacePane


class MainScreen(Screen[None]):
    def compose(self) -> ComposeResult:
        yield HeaderLine()
        with Horizontal(id="panes"):
            yield ExplorerPane(id="explorer-pane")
            yield WorkspacePane()
            with Vertical(id="evidence-container"):
                yield Static("Evidence", id="evidence-title", classes="pane-title")
                yield EvidencePane(id="evidence-pane")
        yield CommandLine()
        yield StatusLine()

    def on_mount(self) -> None:
        self.apply_layout_mode(self.app.layout_mode)  # type: ignore[attr-defined]

    def refresh_from_state(self, old: TuiState | None, new: TuiState) -> None:
        self.query_one(HeaderLine).refresh_from_state(new)
        self.query_one(ExplorerPane).refresh_from_state(new)
        self.query_one(EvidencePane).refresh_from_state(new)
        self.query_one(StatusLine).refresh_from_state(new)
        if old is None or len(new.activity) > len(old.activity):
            self.query_one(WorkspacePane).append_entry(new.activity[-1], new)

    def apply_layout_mode(self, mode: str) -> None:
        panes = self.query_one("#panes", Horizontal)
        panes.set_class(mode == "wide", "mode-wide")
        panes.set_class(mode == "medium", "mode-medium")
        panes.set_class(mode == "narrow", "mode-narrow")
