"""``kairos show`` — full detail for one artifact, optionally scoped to one locator."""

from __future__ import annotations

from pathlib import Path

from kairos.domain.errors import ArtifactNotFoundError
from kairos.domain.locators import locator_from_json, parse_locator_str
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.repositories import get_artifact, list_spans_for_artifact
from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary, SpanResult
from kairos.schemas.provenance import build_envelope
from kairos.services.context import RuntimeContext


def show(ctx: RuntimeContext, artifact_id: str, *, locator: str | None = None) -> ArtifactDetail:
    wanted_locator = parse_locator_str(locator) if locator is not None else None

    with session_scope(ctx.session_factory) as session:
        artifact_row = get_artifact(session, artifact_id)
        if artifact_row is None:
            raise ArtifactNotFoundError(f"No artifact with id: {artifact_id}")

        source_path = ctx.workspace.relative_path(Path(artifact_row.original_path))
        artifact_summary = ArtifactSummary(
            id=artifact_row.id,
            sha256=artifact_row.sha256,
            source_path=source_path,
            kind=artifact_row.kind,
            size_bytes=artifact_row.size_bytes,
            ingested_at=artifact_row.ingested_at,
            parser_name=artifact_row.parser_name,
            parser_version=artifact_row.parser_version,
            parse_status=artifact_row.parse_status,
        )

        span_rows = list_spans_for_artifact(session, artifact_id)
        spans: list[SpanResult] = []
        for span_row in span_rows:
            span_locator = locator_from_json(span_row.locator_json)
            if wanted_locator is not None and span_locator != wanted_locator:
                continue
            envelope = build_envelope(
                artifact_id=artifact_row.id,
                source_path=source_path,
                artifact_kind=artifact_row.kind,
                locator=span_locator,
                parser_name=artifact_row.parser_name,
                parser_version=artifact_row.parser_version,
                layer="extracted",
            )
            spans.append(
                SpanResult(
                    span_id=span_row.id,
                    span_kind=span_row.span_kind,
                    ordinal=span_row.ordinal,
                    parent_span_id=span_row.parent_span_id,
                    text_content=span_row.text_content,
                    provenance=envelope,
                )
            )

        return ArtifactDetail(artifact=artifact_summary, spans=spans)
