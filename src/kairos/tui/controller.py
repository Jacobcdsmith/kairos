"""Command dispatch: parsed ``Command`` -> exactly one existing service call
-> new ``TuiState``. No SQL, no FTS, no ORM, no relation/derivation logic
lives here — only translation between the command grammar and
``kairos.services.*``'s typed results.
"""

from __future__ import annotations

import dataclasses
from datetime import UTC, datetime

from kairos.domain.errors import KairosError
from kairos.domain.ids import new_id
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.orm import (
    ArtifactRow,
    CoherenceWellRow,
    EntityRow,
    RelationRow,
    SourceSpanRow,
)
from kairos.schemas.dashboard import DashboardResult, ParseBreakdown
from kairos.services.activity import recent_events
from kairos.services.artifacts import list_artifacts as list_artifacts_service
from kairos.services.config_query import get_config_symbol
from kairos.services.context import RuntimeContext
from kairos.services.doctor import run_doctor
from kairos.services.ingest import ingest as ingest_service
from kairos.services.logs_query import query_logs
from kairos.services.notes import add_note, list_notes
from kairos.services.search import search as search_service
from kairos.services.show import show as show_service
from kairos.services.trace import trace as trace_service
from kairos.services.wells import list_all_wells, show_well
from kairos.tui.commands import Command, CommandParseError, parse
from kairos.tui.state import ActivityEntry, Mode, Selection, TuiState

_MODE_BY_COMMAND: dict[str, Mode] = {
    "home": "home",
    "artifacts": "artifacts",
    "search": "search",
    "show": "show",
    "trace": "trace",
    "well": "well",
    "config": "config",
    "logs": "logs",
    "doctor": "doctor",
    "history": "history",
    "help": "help",
    "note": "notes",
}


def dispatch_text(runtime_ctx: RuntimeContext, state: TuiState, text: str) -> TuiState:
    """Parse and run one command line, always returning a new state — never
    raises. Parse errors and service errors both land as a "error" activity
    entry with a status-line message, per the spec's "actionable errors, no
    traceback" requirement.
    """
    try:
        command = parse(text)
    except CommandParseError as exc:
        return _record(state, mode=state.mode, command=text, status="error", summary=str(exc))

    if command.name == "quit":
        return _record(state, mode=state.mode, command=text, status="success", summary="quit")

    if command.name == "refresh":
        last = next((e for e in reversed(state.activity) if e.status == "success"), None)
        if last is None:
            return _record(
                state, mode=state.mode, command=text, status="error", summary="Nothing to refresh."
            )
        return dispatch_text(runtime_ctx, state, last.command)

    try:
        return _dispatch(runtime_ctx, state, command)
    except KairosError as exc:
        mode = _MODE_BY_COMMAND.get(command.name, state.mode)
        return _record(state, mode=mode, command=text, status="error", summary=str(exc))


def _dispatch(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    handler = _HANDLERS.get(command.name)
    if handler is None:
        return _record(
            state,
            mode=state.mode,
            command=command.raw,
            status="error",
            summary=f"Not yet wired: :{command.name}",
        )
    return handler(runtime_ctx, state, command)


def _record(
    state: TuiState,
    *,
    mode: Mode,
    command: str,
    status: str,
    summary: str,
    last_result: object = None,
    selection: Selection | None = None,
) -> TuiState:
    entry = ActivityEntry(
        id=new_id(),
        timestamp=datetime.now(UTC),
        command=command,
        mode=mode,
        status=status,  # type: ignore[arg-type]
        summary=summary,
    )
    return dataclasses.replace(
        state,
        mode=mode,
        activity=(*state.activity, entry),
        status="error" if status == "error" else "idle",
        status_message=summary,
        last_result=last_result,
        selection=selection if selection is not None else state.selection,
    )


def _home(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    events = recent_events(runtime_ctx)
    with session_scope(runtime_ctx.session_factory) as session:
        from sqlalchemy import func, select

        total_artifacts = session.scalar(select(func.count(ArtifactRow.id))) or 0
        total_entities = session.scalar(select(func.count(EntityRow.id))) or 0
        total_relations = session.scalar(select(func.count(RelationRow.id))) or 0
        total_spans = session.scalar(select(func.count(SourceSpanRow.id))) or 0
        total_wells = session.scalar(select(func.count(CoherenceWellRow.id))) or 0

        # Breakdown by kind
        kind_rows = session.execute(
            select(
                ArtifactRow.kind,
                func.count(ArtifactRow.id),
                func.count().filter(ArtifactRow.parse_status == "ok"),
                func.count().filter(ArtifactRow.parse_status != "ok"),
            ).group_by(ArtifactRow.kind)
        ).all()
        breakdown = [
            ParseBreakdown(kind=k, count=c, status_ok=ok, status_error=err)
            for k, c, ok, err in kind_rows
        ]
        parse_errors = sum(b.status_error for b in breakdown)

    dashboard = DashboardResult(
        total_artifacts=total_artifacts,
        total_entities=total_entities,
        total_relations=total_relations,
        total_spans=total_spans,
        total_wells=total_wells,
        artifacts_by_kind=breakdown,
        parse_errors=parse_errors,
        workspace_name=runtime_ctx.workspace.root.name,
        recent_activity=events[:5],
    )
    return _record(
        state,
        mode="home",
        command=command.raw,
        status="success",
        summary=f"{total_artifacts} artifacts, {total_entities} entities, {total_relations} relations",
        last_result=dashboard,
    )


def _artifacts(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    kind = command.args[0] if command.args else None
    results = list_artifacts_service(runtime_ctx, kind=kind)
    return _record(
        state,
        mode="artifacts",
        command=command.raw,
        status="success",
        summary=f"{len(results)} artifact(s)",
        last_result=results,
    )


def _search(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    if not command.args:
        raise KairosError("Usage: :search <query>")
    query = command.args[0]
    result = search_service(runtime_ctx, query, well=state.active_well)
    return _record(
        state,
        mode="search",
        command=command.raw,
        status="success",
        summary=f"{len(result.hits)} hit(s) for {query!r}",
        last_result=result,
    )


def _show(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    if not command.args:
        raise KairosError("Usage: :show <artifact-id>")
    artifact_id = command.args[0]
    locator = command.args[1] if len(command.args) > 1 else None
    detail = show_service(runtime_ctx, artifact_id, locator=locator)
    return _record(
        state,
        mode="show",
        command=command.raw,
        status="success",
        summary=f"{detail.artifact.source_path} ({len(detail.spans)} span(s))",
        last_result=detail,
        selection=Selection(kind="artifact", id=artifact_id, origin_view="show"),
    )


def _trace(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    if not command.args:
        raise KairosError("Usage: :trace <term-or-id>")
    term = command.args[0]
    result = trace_service(runtime_ctx, term, well=state.active_well)
    return _record(
        state,
        mode="trace",
        command=command.raw,
        status="success",
        summary=f"{len(result.nodes)} node(s), {len(result.edges)} edge(s) for {term!r}",
        last_result=result,
    )


def _config(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    if not command.args:
        raise KairosError("Usage: :config <symbol>")
    symbol_result = get_config_symbol(runtime_ctx, command.args[0])
    return _record(
        state,
        mode="config",
        command=command.raw,
        status="success",
        summary=f"symbol {symbol_result.symbol}",
        last_result=symbol_result,
    )


def _logs(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    if not command.args:
        raise KairosError("Usage: :logs <query>")
    hits = query_logs(runtime_ctx, command.args[0])
    return _record(
        state,
        mode="logs",
        command=command.raw,
        status="success",
        summary=f"{len(hits)} log line(s)",
        last_result=hits,
    )


def _doctor(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    report = run_doctor(runtime_ctx)
    status = "success" if report.healthy else "error"
    return _record(
        state,
        mode="doctor",
        command=command.raw,
        status=status,
        summary="all checks passed" if report.healthy else "one or more checks failed",
        last_result=report,
    )


def _history(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    return _record(
        state,
        mode="history",
        command=command.raw,
        status="success",
        summary=f"{len(state.activity)} entr(ies) this session",
    )


def _help(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    return _record(state, mode="help", command=command.raw, status="success", summary="help")


def _tutorial(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    return _record(
        state,
        mode=state.mode,
        command=command.raw,
        status="success",
        summary="Press 't' to open the tutorial overlay, or Esc to close it.",
    )


def _well(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    sub = command.args[0] if command.args else "list"
    if sub == "list":
        wells = list_all_wells(runtime_ctx)
        return _record(
            state,
            mode="well",
            command=command.raw,
            status="success",
            summary=f"{len(wells)} well(s)",
            last_result=wells,
        )
    if sub == "use":
        if len(command.args) < 2:
            raise KairosError("Usage: :well use <name>")
        name = command.args[1]
        show_well(runtime_ctx, name)  # raises WellNotFoundError if absent
        new_state = dataclasses.replace(state, active_well=name)
        return _record(
            new_state,
            mode="well",
            command=command.raw,
            status="success",
            summary=f"active well: {name}",
        )
    if sub == "clear":
        new_state = dataclasses.replace(state, active_well=None)
        return _record(
            new_state, mode="well", command=command.raw, status="success", summary="well cleared"
        )
    if sub == "show":
        if len(command.args) < 2:
            raise KairosError("Usage: :well show <name>")
        detail = show_well(runtime_ctx, command.args[1])
        return _record(
            state,
            mode="well",
            command=command.raw,
            status="success",
            summary=f"{detail.well.name} ({detail.well.member_count} member(s))",
            last_result=detail,
        )
    raise KairosError(f"Usage: :well list|use <name>|clear|show <name> (got {sub!r})")


def _note(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    if not command.args:
        raise KairosError("Usage: :note list <target-id> | :note add <target-id> <text>")
    sub, rest = command.args[0], command.args[1:]
    if sub == "list":
        if not rest:
            raise KairosError("Usage: :note list <target-id>")
        notes = list_notes(runtime_ctx, rest[0])
        return _record(
            state,
            mode="notes",
            command=command.raw,
            status="success",
            summary=f"{len(notes)} note(s) on {rest[0]}",
            last_result=notes,
        )
    if sub == "add":
        if len(rest) < 2:
            raise KairosError("Usage: :note add <target-id> <text>")
        add_note(runtime_ctx, rest[0], rest[1])
        notes = list_notes(runtime_ctx, rest[0])
        return _record(
            state,
            mode="notes",
            command=command.raw,
            status="success",
            summary=f"note added ({len(notes)} total on {rest[0]})",
            last_result=notes,
        )
    raise KairosError(f"Usage: :note list <target-id> | :note add <target-id> <text> (got {sub!r})")


def _ingest(runtime_ctx: RuntimeContext, state: TuiState, command: Command) -> TuiState:
    from pathlib import Path

    path_arg = command.args[0] if command.args else "."
    recursive = "--recursive" in command.args or "-r" in command.args

    path = Path(path_arg)
    if not path.is_absolute():
        path = runtime_ctx.workspace.root / path

    report = ingest_service(runtime_ctx, path, recursive=recursive)
    total = len(report.outcomes)
    new_count = sum(1 for o in report.outcomes if not o.already_ingested)
    diag_count = sum(len(o.diagnostics) for o in report.outcomes)

    summary_parts = [f"{new_count} new artifact(s)"]
    if total != new_count:
        summary_parts.append(f"{total - new_count} already ingested")
    if diag_count:
        summary_parts.append(f"{diag_count} diagnostic(s)")

    return _record(
        state,
        mode="artifacts",
        command=command.raw,
        status="success",
        summary=", ".join(summary_parts),
        last_result=list_artifacts_service(runtime_ctx),
    )


_HANDLERS = {
    "home": _home,
    "artifacts": _artifacts,
    "search": _search,
    "show": _show,
    "trace": _trace,
    "config": _config,
    "logs": _logs,
    "doctor": _doctor,
    "history": _history,
    "help": _help,
    "tutorial": _tutorial,
    "well": _well,
    "note": _note,
    "ingest": _ingest,
}
