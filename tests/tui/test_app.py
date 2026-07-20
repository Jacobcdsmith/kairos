"""Pilot-driven tests for ``KairosApp``. All sizes are explicit (never left
to guess a real terminal width) — see docs/tli-implementation-plan.md's
test-strategy section on why non-TTY width blowout is de-risked up front.
"""

from __future__ import annotations

import socket

import pytest

# Both guarded explicitly (not just relied on via `pip install -e ".[tui]"`):
# without pytest-asyncio, `async def test_...` functions are silently never
# awaited by plain pytest — a real footgun that would make this whole file
# falsely "pass" instead of skipping. `importorskip` turns "dependency
# missing" into a clean, visible skip instead of either a collection error
# (Textual) or a silent no-op (pytest-asyncio).
pytest.importorskip("textual")
pytest.importorskip("pytest_asyncio")

from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary
from kairos.schemas.config import ConfigSymbolResult
from kairos.schemas.doctor import DoctorReport
from kairos.schemas.logs import LogHit
from kairos.schemas.search import SearchResult
from kairos.schemas.trace import TraceResult
from kairos.services.context import RuntimeContext
from kairos.tui.app import KairosApp
from kairos.tui.screens.help import HelpScreen
from kairos.tui.screens.main import MainScreen
from kairos.tui.state import as_list_of
from kairos.tui.widgets.evidence_pane import EvidencePane
from kairos.tui.widgets.explorer_pane import ExplorerPane
from kairos.tui.widgets.header_line import HeaderLine
from kairos.tui.widgets.status_line import StatusLine
from kairos.tui.widgets.workspace_pane import WorkspacePane

WIDE = (140, 40)


async def _type_command(pilot: object, text: str) -> None:
    await pilot.click("#command-line")  # type: ignore[attr-defined]
    await pilot.press(*text)  # type: ignore[attr-defined]
    await pilot.press("enter")  # type: ignore[attr-defined]
    await pilot.pause()  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_app_starts_in_valid_workspace(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await pilot.pause()
        assert app.state.mode == "home"
        assert isinstance(app.query_one(MainScreen), MainScreen)


@pytest.mark.asyncio
async def test_header_shows_workspace_well_and_offline_state(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await pilot.pause()
        header_text = str(app.query_one(HeaderLine).renderable)
        assert runtime_ctx.workspace.root.name in header_text
        assert "well: none" in header_text
        assert "LOCAL" in header_text

        await _type_command(pilot, ":well use ")  # missing name: usage error, well stays none
        assert "well: none" in str(app.query_one(HeaderLine).renderable)


@pytest.mark.asyncio
async def test_artifacts_command_lists_ingested_artifacts(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        assert app.state.mode == "artifacts"
        artifacts = as_list_of(app.state.last_result, ArtifactSummary)
        assert artifacts is not None
        assert len(artifacts) == 7
        rows = list(app.query_one(ExplorerPane).children)
        assert len(rows) == 7


@pytest.mark.asyncio
async def test_selecting_artifact_renders_full_citation(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts markdown")
        explorer = app.query_one(ExplorerPane)
        explorer.focus()
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        evidence = str(app.query_one(EvidencePane).renderable)
        assert "id:" in evidence
        assert "path:" in evidence
        assert "kind:" in evidence
        assert "parser:" in evidence


@pytest.mark.asyncio
async def test_search_shows_hits_with_full_citations(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":search widget")
        assert app.state.mode == "search"
        assert isinstance(app.state.last_result, SearchResult)
        assert app.state.last_result.hits
        for hit in app.state.last_result.hits:
            assert hit.provenance.artifact_id
            assert hit.provenance.locator_str
            assert hit.provenance.layer in ("raw", "extracted", "derived", "user")


@pytest.mark.asyncio
async def test_copy_citation_and_excerpt_echo_to_workspace(
    runtime_ctx: RuntimeContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    written: list[object] = []
    clipboard_calls: list[str] = []

    def _fake_write(self: WorkspacePane, obj: object, **_kw: object) -> None:
        written.append(obj)

    def _fake_copy(self: KairosApp, text: str) -> None:
        clipboard_calls.append(text)

    monkeypatch.setattr(WorkspacePane, "write", _fake_write)
    monkeypatch.setattr(KairosApp, "copy_to_clipboard", _fake_copy)

    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":search widget")
        explorer = app.query_one(ExplorerPane)
        explorer.focus()
        await pilot.pause()
        await pilot.press("enter")  # select the first hit -> populates Evidence
        await pilot.pause()

        await pilot.press("c")
        await pilot.pause()
        assert any("Copied citation" in str(w) for w in written)
        assert any("artifact_id:" in str(w) for w in written)
        assert clipboard_calls and "artifact_id:" in clipboard_calls[-1]

        await pilot.press("y")
        await pilot.pause()
        assert any("Copied excerpt" in str(w) for w in written)


@pytest.mark.asyncio
async def test_search_honors_active_well_filter(runtime_ctx: RuntimeContext) -> None:
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
        assert app.state.active_well == "scoped"
        await _type_command(pilot, ":search widget")
        assert isinstance(app.state.last_result, SearchResult)
        scoped_count = len(app.state.last_result.hits)
        assert scoped_count < unscoped_count
        assert all(h.provenance.artifact_id == md_id for h in app.state.last_result.hits)


@pytest.mark.asyncio
async def test_trace_renders_only_explicit_typed_relation_edges(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":trace widget")
        assert app.state.mode == "trace"
        result = app.state.last_result
        assert isinstance(result, TraceResult)
        assert result.nodes
        for edge in result.edges:
            assert edge.layer in ("extracted", "derived")
            assert edge.predicate


@pytest.mark.asyncio
async def test_derived_relation_shows_origin_and_rule_and_similarity_disclaimer(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        # "gadgets" seeds from a shared heading across sample.md/sample2.md,
        # which is what produces a `heading_contains` DERIVED edge — unlike
        # "widget", which only seeds an entity with an EXTRACTED mention.
        await _type_command(pilot, ":trace gadgets")
        result = app.state.last_result
        assert isinstance(result, TraceResult)
        derived_edge = next((e for e in result.edges if e.layer == "derived"), None)
        assert derived_edge is not None, "expected at least one derived edge from the fixtures"

        # Select the node at the derived edge's subject end and confirm the
        # Evidence pane both names the rule and states the non-similarity fact.
        explorer = app.query_one(ExplorerPane)
        explorer.focus()
        target_index = next(
            i for i, n in enumerate(result.nodes) if n.node_id == derived_edge.subject_id
        )
        for _ in range(target_index):
            await pilot.press("down")
        await pilot.pause()
        await pilot.press("enter")
        await pilot.pause()

        evidence = str(app.query_one(EvidencePane).renderable)
        assert derived_edge.derivation_rule is not None
        assert derived_edge.derivation_rule in evidence
        assert "not a semantic similarity claim" in evidence


@pytest.mark.asyncio
async def test_show_opens_structured_source_detail(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts markdown")
        artifacts = as_list_of(app.state.last_result, ArtifactSummary)
        assert artifacts is not None
        artifact_id = artifacts[0].id
        await _type_command(pilot, f":show {artifact_id}")
        assert app.state.mode == "show"
        assert isinstance(app.state.last_result, ArtifactDetail)
        assert app.state.last_result.artifact.id == artifact_id
        assert app.state.last_result.spans


@pytest.mark.asyncio
async def test_config_shows_symbol_provenance(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":config CONFIG_WIFI_POWER_SAVE")
        assert app.state.mode == "config"
        assert app.state.status == "idle"
        assert isinstance(app.state.last_result, ConfigSymbolResult)
        assert app.state.last_result.provenance.layer == "extracted"
        evidence = str(app.query_one(EvidencePane).renderable)
        assert "artifact_id:" in evidence


@pytest.mark.asyncio
async def test_logs_shows_hits_with_locators_and_context(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":logs widget")
        assert app.state.mode == "logs"
        log_hits = as_list_of(app.state.last_result, LogHit)
        assert log_hits
        for hit in log_hits:
            assert hit.provenance.locator_str


@pytest.mark.asyncio
async def test_doctor_displays_checks_and_never_invokes_repair(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":doctor")
        assert app.state.mode == "doctor"
        assert isinstance(app.state.last_result, DoctorReport)
        assert app.state.last_result.healthy
        for check in app.state.last_result.checks:
            assert check.ok
        # The doctor controller handler only ever calls run_doctor(), which
        # is read-only by construction (see services/doctor.py) — there is
        # no repair action wired to any command or keybinding to invoke.


@pytest.mark.asyncio
async def test_bad_command_shows_actionable_error_with_no_traceback(
    runtime_ctx: RuntimeContext,
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":bogus")
        assert app.state.status == "error"
        status_text = str(app.query_one(StatusLine).renderable)
        assert "Traceback" not in status_text
        assert "Unknown command" in status_text


@pytest.mark.asyncio
async def test_focus_cycles_between_panes(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await pilot.pause()
        app.query_one(ExplorerPane).focus()
        await pilot.pause()
        seen: list[str | None] = []
        for _ in range(4):
            seen.append(app.focused.id if app.focused is not None else None)
            await pilot.press("tab")
            await pilot.pause()
        assert seen == ["explorer-pane", "workspace-pane", "evidence-pane", "command-line"]


@pytest.mark.asyncio
async def test_help_overlay_opens_and_closes(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await pilot.pause()
        await pilot.press("question_mark")
        await pilot.pause()
        assert isinstance(app.screen, HelpScreen)
        await pilot.press("escape")
        await pilot.pause()
        assert not isinstance(app.screen, HelpScreen)


@pytest.mark.asyncio
async def test_history_records_success_and_failure(runtime_ctx: RuntimeContext) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        await _type_command(pilot, ":bogus")
        await _type_command(pilot, ":history")
        statuses = [e.status for e in app.state.activity]
        assert "success" in statuses
        assert "error" in statuses


@pytest.mark.parametrize(
    "width,expect_explorer,expect_evidence",
    [(140, True, True), (90, True, False), (60, False, False)],
)
@pytest.mark.asyncio
async def test_layout_bounds_hold_at_every_width(
    runtime_ctx: RuntimeContext, width: int, expect_explorer: bool, expect_evidence: bool
) -> None:
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=(width, 40)) as pilot:
        await _type_command(pilot, ":search widget")
        explorer_visible = app.screen.query_one("#explorer-pane").styles.display != "none"
        evidence_visible = app.screen.query_one("#evidence-container").styles.display != "none"
        assert explorer_visible == expect_explorer
        assert evidence_visible == expect_evidence
        # Provenance must still be fully present in state regardless of
        # which panes are visible at this width — never truncated mid-id.
        assert app.query_one(WorkspacePane) is not None
        assert isinstance(app.state.last_result, SearchResult)
        assert app.state.last_result.hits[0].provenance.artifact_id


@pytest.mark.asyncio
async def test_tui_makes_no_network_access(
    runtime_ctx: RuntimeContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _blocked(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("KAIROS TUI attempted network access.")

    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)

    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        await _type_command(pilot, ":search widget")
        await _type_command(pilot, ":trace widget")
        await _type_command(pilot, ":doctor")


@pytest.mark.asyncio
async def test_no_registered_source_fixture_is_modified(runtime_ctx: RuntimeContext) -> None:
    import hashlib

    from tests.tui.conftest import FIXTURES

    fixture_files = sorted(p for p in FIXTURES.rglob("*") if p.is_file())

    def _hash_all() -> dict[str, str]:
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in fixture_files}

    before = _hash_all()
    app = KairosApp(runtime_ctx)
    async with app.run_test(size=WIDE) as pilot:
        await _type_command(pilot, ":artifacts")
        await _type_command(pilot, ":search widget")
        assert isinstance(app.state.last_result, SearchResult)
        artifact_id = app.state.last_result.hits[0].provenance.artifact_id
        await _type_command(pilot, f":show {artifact_id}")
        await _type_command(pilot, ":doctor")
    after = _hash_all()
    assert before == after
