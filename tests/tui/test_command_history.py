"""Command history: JSONL persistence roundtrip, hint text, and the
controller-level wiring that feeds the command line's ↑/↓ cycling.
"""

from __future__ import annotations

from pathlib import Path

from kairos.services.context import RuntimeContext
from kairos.tui.commands import (
    append_history,
    clear_history,
    hint_text,
    history_file_path,
    load_history,
)
from kairos.tui.controller import dispatch_text
from kairos.tui.state import TuiState


def test_history_roundtrip_add_and_retrieve(tmp_path: Path) -> None:
    assert load_history(tmp_path) == []

    append_history(tmp_path, ":search widget", success=True)
    append_history(tmp_path, ":bogus", success=False)

    records = load_history(tmp_path)
    assert [r.command for r in records] == [":search widget", ":bogus"]
    assert [r.success for r in records] == [True, False]
    assert history_file_path(tmp_path).exists()


def test_history_clear_empties_the_file(tmp_path: Path) -> None:
    append_history(tmp_path, ":search widget", success=True)
    assert load_history(tmp_path)

    clear_history(tmp_path)
    assert load_history(tmp_path) == []


def test_history_load_skips_corrupt_lines(tmp_path: Path) -> None:
    path = history_file_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text('not json\n{"timestamp": "bad", "command": "x", "success": true}\n')
    append_history(tmp_path, ":search widget", success=True)

    records = load_history(tmp_path)
    assert [r.command for r in records] == [":search widget"]


def test_history_clear_on_missing_file_is_a_no_op(tmp_path: Path) -> None:
    clear_history(tmp_path)  # must not raise
    assert load_history(tmp_path) == []


def test_append_history_never_raises_on_filesystem_error(tmp_path: Path) -> None:
    # A file sits where the .kairos directory needs to go, so mkdir fails —
    # history is a convenience feature and must fail closed, not take down
    # command dispatch (which calls this after every command).
    (tmp_path / ".kairos").write_text("not a directory")
    append_history(tmp_path, ":search widget", success=True)  # must not raise
    assert load_history(tmp_path) == []


def test_clear_history_never_raises_on_filesystem_error(tmp_path: Path) -> None:
    history_dir = tmp_path / ".kairos"
    history_dir.mkdir()
    (history_dir / ".tui_history").mkdir()  # a directory, not a file
    clear_history(tmp_path)  # must not raise


def test_hint_text_for_partial_and_full_commands() -> None:
    assert hint_text("") == ""
    assert hint_text("hello") == ""
    assert hint_text(":") == ""
    assert hint_text(":sear").startswith(":search —")
    assert hint_text(":search").startswith(":search —")
    assert hint_text(":search foo").startswith(":search —")


def test_hint_text_for_ambiguous_prefix_lists_candidates() -> None:
    hint = hint_text(":h")
    assert hint.startswith("possible:")
    assert ":home" in hint
    assert ":history" in hint
    assert ":help" in hint


def test_hint_text_for_unknown_command_is_empty() -> None:
    assert hint_text(":zzz") == ""


def test_dispatch_text_appends_to_state_and_disk_history(runtime_ctx: RuntimeContext) -> None:
    state = TuiState(workspace_path=runtime_ctx.workspace.root)
    state = dispatch_text(runtime_ctx, state, ":artifacts")
    state = dispatch_text(runtime_ctx, state, ":bogus")

    assert state.command_history == (":artifacts", ":bogus")
    records = load_history(runtime_ctx.workspace.root)
    assert [r.command for r in records] == [":artifacts", ":bogus"]
    assert [r.success for r in records] == [True, False]


def test_dispatch_text_survives_history_write_failure(runtime_ctx: RuntimeContext) -> None:
    # A directory sits where the history file needs to go, so the append
    # write fails — dispatch (and the in-memory history it drives the
    # command line's ↑/↓ from) must not be affected.
    (runtime_ctx.workspace.root / ".kairos" / ".tui_history").mkdir()
    state = TuiState(workspace_path=runtime_ctx.workspace.root)
    state = dispatch_text(runtime_ctx, state, ":artifacts")
    assert state.mode == "artifacts"
    assert state.command_history == (":artifacts",)


def test_history_clear_command_wipes_state_and_disk(runtime_ctx: RuntimeContext) -> None:
    state = TuiState(workspace_path=runtime_ctx.workspace.root)
    state = dispatch_text(runtime_ctx, state, ":artifacts")
    assert state.command_history

    state = dispatch_text(runtime_ctx, state, ":history --clear")
    assert state.command_history == ()
    assert load_history(runtime_ctx.workspace.root) == []
    assert state.status == "idle"
    assert state.activity[-1].status == "success"
    assert "cleared" in (state.status_message or "")


def test_dispatch_text_records_command_runtime(runtime_ctx: RuntimeContext) -> None:
    state = TuiState(workspace_path=runtime_ctx.workspace.root)
    state = dispatch_text(runtime_ctx, state, ":artifacts")
    assert state.last_command_label == "artifacts"
    assert state.last_command_ms is not None
    assert state.last_command_ms >= 0
