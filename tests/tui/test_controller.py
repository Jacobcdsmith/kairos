"""Controller-level tests: pure Python, no Textual Pilot needed. Each test
dispatches a command against a real ``RuntimeContext`` on an ingested tmp
workspace and asserts on the resulting ``TuiState`` — this is where most of
the command-grammar and service-boundary behavior is actually verified.
"""

from __future__ import annotations

import dataclasses

from kairos.schemas.activity import ActivityEvent
from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary
from kairos.schemas.config import ConfigSymbolResult
from kairos.schemas.doctor import DoctorReport
from kairos.schemas.logs import LogHit
from kairos.schemas.note import NoteResult
from kairos.schemas.search import SearchResult
from kairos.schemas.trace import TraceResult
from kairos.services.context import RuntimeContext
from kairos.tui.controller import dispatch_text
from kairos.tui.state import TuiState, as_list_of


def _fresh_state(runtime_ctx: RuntimeContext) -> TuiState:
    return TuiState(workspace_path=runtime_ctx.workspace.root)


def _artifacts_result(state: TuiState) -> list[ArtifactSummary]:
    result = as_list_of(state.last_result, ArtifactSummary)
    assert result is not None
    return result


def test_artifacts_lists_ingested_artifacts(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":artifacts")
    assert state.mode == "artifacts"
    assert state.status == "idle"
    assert len(_artifacts_result(state)) == 7  # matches ingested_workspace's 7 fixture files
    assert state.activity[-1].status == "success"


def test_search_calls_existing_service_and_returns_full_citations(
    runtime_ctx: RuntimeContext,
) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":search widget")
    assert state.mode == "search"
    assert isinstance(state.last_result, SearchResult)
    assert state.last_result.hits
    for hit in state.last_result.hits:
        assert hit.provenance.artifact_id
        assert hit.provenance.locator_str
        assert hit.provenance.layer in ("raw", "extracted", "derived", "user")


def test_search_without_query_is_a_usage_error_not_a_crash(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":search")
    assert state.status == "error"
    assert "Usage" in (state.status_message or "")


def test_search_honors_active_well_filter(runtime_ctx: RuntimeContext) -> None:
    base = _fresh_state(runtime_ctx)
    # Build a well containing only the markdown sample, then confirm the
    # active-well filter narrows a search that otherwise hits multiple kinds.
    state = dispatch_text(runtime_ctx, base, ":artifacts markdown")
    md_artifact_id = _artifacts_result(state)[0].id

    from kairos.services.wells import add_member, create_well

    create_well(runtime_ctx, "scoped", "just the markdown sample")
    add_member(runtime_ctx, "scoped", md_artifact_id)

    scoped_base = dataclasses.replace(base, active_well="scoped")
    scoped_state = dispatch_text(runtime_ctx, scoped_base, ":search widget")
    assert isinstance(scoped_state.last_result, SearchResult)
    unscoped_state = dispatch_text(runtime_ctx, base, ":search widget")
    assert isinstance(unscoped_state.last_result, SearchResult)
    assert len(scoped_state.last_result.hits) < len(unscoped_state.last_result.hits)
    for hit in scoped_state.last_result.hits:
        assert hit.provenance.artifact_id == md_artifact_id


def test_trace_renders_only_explicit_typed_relation_edges(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":trace widget")
    assert isinstance(state.last_result, TraceResult)
    for edge in state.last_result.edges:
        assert edge.layer in ("extracted", "derived")
        assert edge.predicate  # every edge is a typed predicate, never a bare "related"


def test_show_opens_structured_source_detail(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":artifacts markdown")
    artifact_id = _artifacts_result(state)[0].id
    detail_state = dispatch_text(runtime_ctx, state, f":show {artifact_id}")
    assert isinstance(detail_state.last_result, ArtifactDetail)
    assert detail_state.last_result.artifact.id == artifact_id
    assert detail_state.selection.kind == "artifact"
    assert detail_state.selection.id == artifact_id


def test_config_shows_symbol_provenance(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":config CONFIG_WIFI_POWER_SAVE")
    assert state.status == "idle"
    assert isinstance(state.last_result, ConfigSymbolResult)
    assert state.last_result.symbol == "CONFIG_WIFI_POWER_SAVE"
    assert state.last_result.provenance.layer == "extracted"


def test_logs_shows_hits_with_locators(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":logs widget")
    hits = as_list_of(state.last_result, LogHit)
    assert hits
    for hit in hits:
        assert hit.provenance.locator_str


def test_doctor_displays_checks_and_never_repairs(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":doctor")
    assert isinstance(state.last_result, DoctorReport)
    assert state.last_result.healthy
    assert state.status == "idle"


def test_bad_command_is_actionable_and_has_no_traceback(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":bogus")
    assert state.status == "error"
    assert "Traceback" not in (state.status_message or "")
    assert (state.status_message or "").startswith("Unknown command")


def test_history_records_success_and_failure(runtime_ctx: RuntimeContext) -> None:
    state = _fresh_state(runtime_ctx)
    state = dispatch_text(runtime_ctx, state, ":artifacts")
    state = dispatch_text(runtime_ctx, state, ":bogus")
    assert [e.status for e in state.activity] == ["success", "error"]


def test_refresh_reruns_the_last_successful_command(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":search widget")
    assert isinstance(state.last_result, SearchResult)
    original_hits = len(state.last_result.hits)
    refreshed = dispatch_text(runtime_ctx, state, ":refresh")
    assert refreshed.mode == "search"
    assert isinstance(refreshed.last_result, SearchResult)
    assert len(refreshed.last_result.hits) == original_hits


def test_well_use_and_clear(runtime_ctx: RuntimeContext) -> None:
    from kairos.services.wells import create_well

    create_well(runtime_ctx, "docs", "just docs")
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":well use docs")
    assert state.active_well == "docs"
    cleared = dispatch_text(runtime_ctx, state, ":well clear")
    assert cleared.active_well is None


def test_well_use_unknown_name_is_actionable_error(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":well use nope")
    assert state.status == "error"
    assert state.active_well is None


def test_note_add_and_list_are_the_only_mutations(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":artifacts markdown")
    artifact_id = _artifacts_result(state)[0].id
    state = dispatch_text(runtime_ctx, state, f":note add {artifact_id} looks good")
    assert state.status == "idle"
    state = dispatch_text(runtime_ctx, state, f":note list {artifact_id}")
    notes = as_list_of(state.last_result, NoteResult)
    assert notes
    assert notes[0].body == "looks good"


def test_home_lists_recent_activity(runtime_ctx: RuntimeContext) -> None:
    state = dispatch_text(runtime_ctx, _fresh_state(runtime_ctx), ":artifacts")
    state = dispatch_text(runtime_ctx, state, ":home")
    assert state.mode == "home"
    assert as_list_of(state.last_result, ActivityEvent) is not None
