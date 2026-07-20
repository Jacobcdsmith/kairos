"""Interactive tutorial overlay: walks through key TUI features step-by-step."""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Static

_TUTORIAL_STEPS = [
    (
        "Welcome to KAIROS TUI",
        "This is your interactive workspace for exploring a local technical corpus.\n\n"
        "Every result carries full provenance: artifact ID, source path, exact locator,\n"
        "parser version, and provenance layer.\n\n"
        "Press Next to learn the layout, or Escape to skip this tutorial.",
    ),
    (
        "The Layout",
        "The TUI has three main panes:\n\n"
        "  Explorer (left)    — Lists items from your current query\n"
        "  Workspace (center) — Shows command output and history\n"
        "  Evidence (right)   — Full citation for the selected item\n\n"
        "At the bottom: command line and status bar with keybindings.",
    ),
    (
        "Commands",
        "Type commands at the bottom prompt:\n\n"
        "  :search <query>    Full-text search across all artifacts\n"
        "  :artifacts         List all ingested files\n"
        "  :show <id>         Show artifact structure\n"
        "  :trace <term>      Trace relations across sources\n"
        "  :well list         Show coherence wells\n"
        "  :help              Show all commands\n\n"
        "Commands start with ':' — unknown input shows an error, never a traceback.",
    ),
    (
        "Navigation",
        "Move between panes and items:\n\n"
        "  Tab / Shift+Tab    Cycle focus between panes\n"
        "  Up / Down          Move selection in focused list\n"
        "  Enter              Inspect selected item in Evidence pane\n"
        "  Ctrl+P             Fuzzy finder (quick artifact search)\n"
        "  /                  Start a search command\n"
        "  w                  Open well picker",
    ),
    (
        "Provenance & Evidence",
        "Every item shows its provenance layer:\n\n"
        "  ○ RAW        — The ingested bytes themselves\n"
        "  ● EXTRACTED  — Deterministic parser output (span, entity)\n"
        "  ◇ DERIVED    — Machine-made link between extracted objects\n"
        "  ✎ USER       — Owner-authored (note, well membership)\n\n"
        "Select any item and the Evidence pane shows the full citation:\n"
        "artifact ID, path, locator, parser, and layer.",
    ),
    (
        "Copy & Export",
        "Quick copy actions:\n\n"
        "  c                  Copy citation for selected item\n"
        "  y                  Copy excerpt/text content\n\n"
        "Copies go to clipboard (via OSC 52) and echo in Workspace pane\n"
        "as a fallback if your terminal doesn't support clipboard escapes.",
    ),
    (
        "Auto-ingest",
        "KAIROS automatically ingests the workspace root on startup.\n\n"
        "Files are deduplicated by SHA256 — re-scanning unchanged files is instant.\n"
        "New or modified files are parsed and indexed.\n\n"
        "You can also ingest manually:\n"
        "  :ingest <path> [--recursive]",
    ),
    (
        "Ready to explore",
        "You're all set. Try these to get started:\n\n"
        "  :artifacts         See what's been ingested\n"
        "  :search <term>     Find text across all sources\n"
        "  :trace <entity>    Follow relations between artifacts\n\n"
        "Press Escape to close this tutorial and start exploring.\n\n"
        "Remember: everything is local, nothing leaves your machine.",
    ),
]


class TutorialScreen(ModalScreen[None]):
    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("right", "next_step", "Next"),
        ("left", "prev_step", "Previous"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._current_step = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="tutorial-container"):
            yield Static("", id="tutorial-title")
            yield Static("", id="tutorial-body")
            yield Static("", id="tutorial-progress")

    def on_mount(self) -> None:
        self._render_step()

    def _render_step(self) -> None:
        title, body = _TUTORIAL_STEPS[self._current_step]
        total = len(_TUTORIAL_STEPS)
        progress = f"Step {self._current_step + 1} of {total}"

        self.query_one("#tutorial-title", Static).update(f"[bold cyan]{title}[/bold cyan]")
        self.query_one("#tutorial-body", Static).update(body)
        self.query_one("#tutorial-progress", Static).update(
            f"[dim]{progress} — ← prev | next → | Esc close[/dim]"
        )

    def action_next_step(self) -> None:
        if self._current_step < len(_TUTORIAL_STEPS) - 1:
            self._current_step += 1
            self._render_step()
        else:
            self.dismiss(None)

    def action_prev_step(self) -> None:
        if self._current_step > 0:
            self._current_step -= 1
            self._render_step()
