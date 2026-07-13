"""``kairos logs <query> [--before N] [--after N] [--level <level>]`` — log search with context."""

from __future__ import annotations

from pathlib import Path

from kairos.domain.locators import locator_from_json
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.fts import search_spans
from kairos.infrastructure.database.repositories import (
    get_artifact,
    get_span,
    list_spans_for_artifact,
)
from kairos.schemas.logs import LogHit
from kairos.schemas.provenance import build_envelope
from kairos.services.context import RuntimeContext

_LOG_LINE_KIND = "log_line"


def query_logs(
    ctx: RuntimeContext,
    query: str,
    *,
    before: int = 0,
    after: int = 0,
    level: str | None = None,
    limit: int = 20,
) -> list[LogHit]:
    with session_scope(ctx.session_factory) as session:
        anchors = search_spans(session, query, kind_filter=_LOG_LINE_KIND, limit=limit)

        selected_span_ids: dict[str, None] = {}  # ordered set, preserving first-seen order
        for anchor in anchors:
            span_row = get_span(session, anchor.span_id)
            if span_row is None:
                continue
            anchor_level = span_row.metadata_json.get("level")
            if level is not None and anchor_level != level:
                continue

            siblings = list_spans_for_artifact(session, anchor.artifact_id)
            log_lines = [s for s in siblings if s.span_kind == _LOG_LINE_KIND]
            index = next((i for i, s in enumerate(log_lines) if s.id == span_row.id), None)
            if index is None:
                selected_span_ids[span_row.id] = None
                continue
            window = log_lines[max(0, index - before) : index + after + 1]
            for span in window:
                selected_span_ids[span.id] = None

        results: list[LogHit] = []
        for span_id in selected_span_ids:
            span_row = get_span(session, span_id)
            if span_row is None:
                continue
            artifact_row = get_artifact(session, span_row.artifact_id)
            if artifact_row is None:
                continue
            envelope = build_envelope(
                artifact_id=artifact_row.id,
                source_path=ctx.workspace.relative_path(Path(artifact_row.original_path)),
                artifact_kind=artifact_row.kind,
                locator=locator_from_json(span_row.locator_json),
                parser_name=artifact_row.parser_name,
                parser_version=artifact_row.parser_version,
                layer="extracted",
            )
            metadata = span_row.metadata_json
            results.append(
                LogHit(
                    line_number=_line_number(span_row.locator_json),
                    timestamp=_opt_str(metadata.get("timestamp")),
                    level=_opt_str(metadata.get("level")),
                    component=_opt_str(metadata.get("component")),
                    message=span_row.text_content,
                    provenance=envelope,
                )
            )
        return results


def _opt_str(value: object) -> str | None:
    return None if value is None else str(value)


def _line_number(locator_json: dict[str, object]) -> int:
    raw = locator_json.get("line_number", 0)
    return int(raw) if isinstance(raw, int | float | str) else 0
