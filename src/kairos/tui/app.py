"""``KairosApp`` — the Textual application entry point for ``kairos tui``.

Owns the single ``TuiState``, dispatches commands through
``kairos.tui.controller`` in a worker thread (never blocking the UI), and
keeps every service call read-mostly per docs/tli-implementation-plan.md.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

from textual import work
from textual.app import App
from textual.binding import Binding
from textual.css.query import NoMatches
from textual.widgets import Input, ListView

from kairos.services.context import RuntimeContext
from kairos.tui import controller
from kairos.tui.screens.fuzzy_finder import FuzzyFinderScreen
from kairos.tui.screens.help import HelpScreen
from kairos.tui.screens.main import MainScreen
from kairos.tui.screens.tutorial import TutorialScreen
from kairos.tui.screens.well_picker import WellPickerScreen
from kairos.tui.state import Selection, TuiState
from kairos.tui.widgets.evidence_pane import EvidencePane, citation_text, excerpt_text
from kairos.tui.widgets.explorer_pane import ExplorerPane
from kairos.tui.widgets.workspace_pane import WorkspacePane

_STYLES_PATH = Path(__file__).parent / "styles" / "kairos.tcss"

_WIDE_MIN = 120
_MEDIUM_MIN = 80

FocusableWidget = ExplorerPane | WorkspacePane | EvidencePane | Input


class KairosApp(App[None]):
    CSS_PATH = str(_STYLES_PATH)

    BINDINGS = [
        Binding("ctrl+p", "open_fuzzy_finder", "Find"),
        Binding("ctrl+r", "history_search", "History"),
        Binding("tab", "cycle_focus(false)", "Cycle pane", show=False),
        Binding("shift+tab", "cycle_focus(true)", "Cycle pane (reverse)", show=False),
        Binding("slash", "start_search", "Search"),
        Binding("w", "open_well_picker", "Wells"),
        Binding("c", "copy_citation", "Copy citation"),
        Binding("y", "copy_excerpt", "Copy excerpt"),
        Binding("r", "refresh_view", "Refresh", show=False),
        Binding("t", "show_tutorial", "Tutorial"),
        Binding("question_mark", "show_help", "Help"),
        Binding("q", "quit_app", "Quit"),
    ]

    def __init__(self, runtime_ctx: RuntimeContext) -> None:
        super().__init__()
        self.runtime_ctx = runtime_ctx
        self._request_id = 0
        self.state = TuiState(workspace_path=runtime_ctx.workspace.root)
        self.layout_mode = "wide"

    def on_mount(self) -> None:
        self.push_screen(MainScreen())
        self._apply_layout_mode()
        show_tutorial = self._auto_ingest_workspace()
        self.run_command(":home")
        if show_tutorial:
            self.call_later(self._show_tutorial_if_first_run)

    def _auto_ingest_workspace(self) -> bool:
        from kairos.services.artifacts import list_artifacts

        was_empty = not list_artifacts(self.runtime_ctx)
        self.run_command(":ingest . --recursive")
        return was_empty

    async def _show_tutorial_if_first_run(self) -> None:
        from kairos.services.artifacts import list_artifacts

        artifacts = list_artifacts(self.runtime_ctx)
        if len(artifacts) <= 7:
            self.push_screen(TutorialScreen())

    def on_resize(self) -> None:
        self._apply_layout_mode()

    def _apply_layout_mode(self) -> None:
        width = self.size.width
        self.layout_mode = (
            "wide" if width >= _WIDE_MIN else "medium" if width >= _MEDIUM_MIN else "narrow"
        )
        try:
            self.query_one(MainScreen).apply_layout_mode(self.layout_mode)
        except NoMatches:
            # A resize event fired before MainScreen (or its children) mounted;
            # MainScreen.on_mount applies the current mode itself once ready.
            return

    # -- command dispatch ---------------------------------------------------

    def run_command(self, text: str) -> None:
        self._request_id += 1
        self._dispatch_worker(text, self._request_id)

    @work(thread=True, exclusive=True, group="dispatch")
    def _dispatch_worker(self, text: str, request_id: int) -> None:
        new_state = controller.dispatch_text(self.runtime_ctx, self.state, text)
        if request_id == self._request_id:
            self.call_from_thread(self._apply_state, new_state)

    def _apply_state(self, new_state: TuiState) -> None:
        old_state = self.state
        self.state = new_state
        self.query_one(MainScreen).refresh_from_state(old_state, new_state)
        if new_state.status_message == "quit":
            self.exit()

    # -- selection (Explorer -> Evidence, no re-query) -----------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        explorer = self.query_one(ExplorerPane)
        if event.list_view is not explorer:
            return
        reference = explorer.selected_reference()
        if reference is None:
            return
        kind, target_id = reference
        new_state = dataclasses.replace(
            self.state,
            selection=Selection(kind=kind, id=target_id, origin_view=self.state.mode),
        )
        self.state = new_state
        self.query_one(MainScreen).refresh_from_state(None, new_state)

    # -- actions --------------------------------------------------------------

    def action_focus_command_line(self) -> None:
        self.query_one("#command-line", Input).focus()

    def action_open_fuzzy_finder(self) -> None:
        def handle_result(item: object) -> None:
            if item is None:
                return
            from kairos.tui.screens.fuzzy_finder import FinderItem

            if isinstance(item, FinderItem) and item.kind == "artifact":
                self.run_command(f":show {item.target_id}")

        self.push_screen(FuzzyFinderScreen(self.runtime_ctx), handle_result)

    def action_start_search(self) -> None:
        command_line = self.query_one("#command-line", Input)
        command_line.value = ":search "
        command_line.focus()
        command_line.action_end()

    def action_open_well_picker(self) -> None:
        def handle_result(result: tuple[str, str | None] | None) -> None:
            if result is None or result[0] == "cancel":
                return
            action, name = result
            if action == "use" and name:
                self.run_command(f":well use {name}")
            elif action == "clear":
                self.run_command(":well clear")

        self.push_screen(WellPickerScreen(self.runtime_ctx), handle_result)

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_show_tutorial(self) -> None:
        self.push_screen(TutorialScreen())

    def action_refresh_view(self) -> None:
        if isinstance(self.focused, Input):
            return
        self.run_command(":refresh")

    def action_history_search(self) -> None:
        self.run_command(":history")

    def action_quit_app(self) -> None:
        if isinstance(self.focused, Input):
            return
        self.exit()

    def action_copy_citation(self) -> None:
        if isinstance(self.focused, Input):
            return
        self._copy_and_announce(citation_text(self.state), "citation")

    def action_copy_excerpt(self) -> None:
        if isinstance(self.focused, Input):
            return
        self._copy_and_announce(excerpt_text(self.state), "excerpt")

    def _copy_and_announce(self, text: str | None, label: str) -> None:
        """Copy via the terminal's own clipboard escape sequence (never a
        shell command) and *always* also echo the plain text into the
        Workspace transcript — the fail-safe the spec requires, since a
        terminal that doesn't support OSC 52 clipboard writes fails silently
        rather than raising, so this is the only reliable "did it copy"
        signal the user gets either way.
        """
        workspace_pane = self.query_one(WorkspacePane)
        if text is None:
            workspace_pane.write(f"(no {label} available for the current selection)")
            return
        self.copy_to_clipboard(text)
        workspace_pane.write(f"Copied {label} (also shown here, in case clipboard is unavailable):")
        workspace_pane.write(text)

    def action_cycle_focus(self, reverse: bool) -> None:
        focusable = self._focusable_widgets()
        if not focusable:
            return
        current = self.focused
        index = next((i for i, w in enumerate(focusable) if w is current), -1)
        step = -1 if reverse else 1
        next_index = (index + step) % len(focusable)
        focusable[next_index].focus()

    def _focusable_widgets(self) -> list[FocusableWidget]:
        widgets: list[FocusableWidget] = []
        for widget_type in (ExplorerPane, WorkspacePane, EvidencePane, Input):
            try:
                widgets.append(self.query_one(widget_type))
            except NoMatches:
                continue
        return widgets
