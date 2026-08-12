"""End-to-end TUI workflows driven through Textual's headless Pilot —
multi-step operator sessions rather than single-command unit checks, per
the v0.2 improvement plan's Phase 5.1 (integration coverage).
"""

from __future__ import annotations

import pytest

pytest.importorskip("textual")
pytest.importorskip("pytest_asyncio")

from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary
from kairos.schemas.note import NoteResult
from kairos.schemas.search import SearchResult
from kairos.services.context import RuntimeContext
from kairos.tui.app import KairosApp
from kairos.tui.commands import load_history
from kairos.tui.state import as_list_of
from kairos.tui.widgets.evidence_pane import EvidencePane
from kairos.tui.widgets.explorer_pane import ExplorerPane
from kairos.tui.widgets.header_line import HeaderLine
from kairos.tui.widgets.status_line import StatusLine

WIDE = (140, 30)


async def _type_command(pilot: object, text: str) -> None:
    await pilot.click("#command-line")  # type: ignore[attr-defined]
    await pilot.press(*text)  # type: ignore[attr-defined]
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_workflow_search_select_show_note(runtime_ctx: RuntimeContext) -> None:
    """search a term -> inspect a hit's full citation -> open its artifact
    in detail -> attach a note -> confirm it round-trips via :note list.
    """
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":search widget")
        assert isinstance(app.state.last_result, SearchResult)
        artifact_id = app.state.last_result.hits[0].provenance.artifact_id

        explorer = app.query_one(ExplorerPane)
        explorer.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()
        evidence_text = str(app.query_one(EvidencePane).renderable)
        assert "artifact_id:" in evidence_text

        await _type_command(pilot, f":show {artifact_id}")
        assert isinstance(app.state.last_result, ArtifactDetail)
        assert app.state.last_result.artifact.id == artifact_id

        await _type_command(pilot, f":note add {artifact_id} looks correct")
        await _type_command(pilot, f":note list {artifact_id}")
        notes = as_list_of(app.state.last_result, NoteResult)
        assert notes is not None
        assert notes[-1].body == "looks correct"

        # The whole session shows up as command history, in order (after the
        # app's own startup commands — auto-ingest and the initial :home).
        assert app.state.command_history[-4:] == (
            ":search widget",
            f":show {artifact_id}",
            f":note add {artifact_id} looks correct",
            f":note list {artifact_id}",
        )


@pytest.mark.asyncio
async def test_workflow_well_switch_narrows_results_mid_session(
    runtime_ctx: RuntimeContext,
) -> None:
    """Search unscoped, create a well scoped to one artifact, switch into
    it, and confirm both the results and the header reflect the new scope
    without restarting the app.
    """
    from kairos.services.wells import add_member, create_well

    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts markdown")
        artifacts = as_list_of(app.state.last_result, ArtifactSummary)
        assert artifacts is not None
        md_id = artifacts[0].id
        create_well(runtime_ctx, "scoped", "only markdown")
        add_member(runtime_ctx, "scoped", md_id)

        await _type_command(pilot, ":search widget")
        assert isinstance(app.state.last_result, SearchResult)
        unscoped_count = len(app.state.last_result.hits)

        await _type_command(pilot, ":well use scoped")
        assert "well: scoped" in str(app.query_one(HeaderLine).renderable)

        await _type_command(pilot, ":search widget")
        assert isinstance(app.state.last_result, SearchResult)
        scoped_count = len(app.state.last_result.hits)
        assert scoped_count < unscoped_count

        await _type_command(pilot, ":well clear")
        assert "well: none" in str(app.query_one(HeaderLine).renderable)


@pytest.mark.asyncio
async def test_workflow_command_history_survives_a_restart(
    runtime_ctx: RuntimeContext,
) -> None:
    """Commands typed in one session are still on disk (and cycle-able via
    ↑) after the app is closed and a fresh KairosApp is opened on the same
    workspace — the whole point of persisting to .kairos/.tui_history.
    """
    first = KairosApp(runtime_ctx)
    async with first.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        await _type_command(pilot, ":search widget")

    on_disk = [r.command for r in load_history(runtime_ctx.workspace.root)]
    assert ":artifacts" in on_disk
    assert ":search widget" in on_disk

    second = KairosApp(runtime_ctx)
    async with second.run_test(size=WIDE) as pilot:
        await pilot.pause()
        assert ":search widget" in second.state.command_history

        from kairos.tui.widgets.command_line import CommandLine

        command_line = second.query_one(CommandLine)
        command_line.focus()
        await pilot.pause()
        # The second session's own startup (:home, and possibly a re-run of
        # the auto-ingest) sits most-recent in history; walk back past it to
        # reach the first session's last command.
        for _ in range(len(second.state.command_history)):
            await pilot.press("up")
            await pilot.pause()
            if command_line.value == ":search widget":
                break
        assert command_line.value == ":search widget"


@pytest.mark.asyncio
async def test_workflow_explorer_goto_line_then_inspect_evidence(
    runtime_ctx: RuntimeContext,
) -> None:
    """Jump straight to a specific row with Ctrl+G, select it, then scroll
    its citation in the Evidence pane with the keyboard.
    """
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        explorer = app.query_one(ExplorerPane)
        explorer.focus()
        await pilot.pause()

        await pilot.press("ctrl+g")
        await pilot.pause()
        await pilot.press("4")
        await pilot.press("enter")
        await pilot.pause()
        assert explorer.index == 3

        await pilot.press("enter")  # select the jumped-to row
        await pilot.pause()
        evidence = app.query_one(EvidencePane)
        assert "id:" in str(evidence.renderable)

        evidence.focus()
        await pilot.pause()
        await pilot.press("down")
        await pilot.press("pagedown")
        await pilot.press("home")
        await pilot.pause()
        assert evidence.scroll_y == 0


@pytest.mark.asyncio
async def test_workflow_error_recovery_then_success(runtime_ctx: RuntimeContext) -> None:
    """A typo'd command shows an actionable error and colors the status
    line red; the corrected command then succeeds, turns the status line
    green, and both attempts land in history in order.
    """
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":serach widget")
        assert app.state.status == "error"
        status_text = str(app.query_one(StatusLine).renderable)
        assert "Unknown command" in status_text
        assert "Traceback" not in status_text

        await _type_command(pilot, ":search widget")
        assert app.state.status == "idle"
        assert isinstance(app.state.last_result, SearchResult)

        assert app.state.command_history[-2:] == (":serach widget", ":search widget")
        records = load_history(runtime_ctx.workspace.root)
        by_command = {r.command: r.success for r in records}
        assert by_command[":serach widget"] is False
        assert by_command[":search widget"] is True
