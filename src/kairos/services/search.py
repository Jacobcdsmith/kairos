"""``kairos search`` — FTS5 full-text search over source span text, scoped by kind/well."""

from __future__ import annotations

from pathlib import Path

from kairos.domain.locators import locator_from_json
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.fts import search_spans
from kairos.infrastructure.database.repositories import get_artifact, get_span
from kairos.schemas.provenance import build_envelope
from kairos.schemas.search import SearchHit, SearchResult
from kairos.services.context import RuntimeContext
from kairos.services.wells_scope import well_artifact_ids


def search(
    ctx: RuntimeContext,
    query: str,
    *,
    kind: str | None = None,
    well: str | None = None,
    limit: int = 20,
) -> SearchResult:
    with session_scope(ctx.session_factory) as session:
        artifact_ids = well_artifact_ids(session, well) if well is not None else None
        hits = search_spans(
            session, query, kind_filter=kind, artifact_ids=artifact_ids, limit=limit
        )

        results: list[SearchHit] = []
        for hit in hits:
            span_row = get_span(session, hit.span_id)
            artifact_row = get_artifact(session, hit.artifact_id)
            if span_row is None or artifact_row is None:
                continue
            source_path = ctx.workspace.relative_path(Path(artifact_row.original_path))
            envelope = build_envelope(
                artifact_id=artifact_row.id,
                source_path=source_path,
                artifact_kind=artifact_row.kind,
                locator=locator_from_json(span_row.locator_json),
                parser_name=artifact_row.parser_name,
                parser_version=artifact_row.parser_version,
                layer="extracted",
            )
            results.append(
                SearchHit(
                    span_id=span_row.id,
                    snippet=hit.snippet,
                    text_content=span_row.text_content,
                    rank=hit.rank,
                    provenance=envelope,
                )
            )

        return SearchResult(query=query, hits=results)
