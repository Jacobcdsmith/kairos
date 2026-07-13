"""FTS5 query helpers. The virtual table has no ORM model, so this module is
the only place that touches ``source_spans_fts`` directly, via Core ``text()``.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from kairos.domain.errors import InvalidSearchQueryError


@dataclass(frozen=True, slots=True)
class FtsHit:
    span_id: str
    artifact_id: str
    span_kind: str
    snippet: str
    rank: float


def search_spans(
    session: Session,
    query: str,
    *,
    kind_filter: str | None = None,
    artifact_ids: list[str] | None = None,
    limit: int = 20,
) -> list[FtsHit]:
    """Full-text search over span text, ranked by FTS5 bm25.

    ``kind_filter`` restricts to a ``span_kind`` (a pre-filter on the
    UNINDEXED column, not part of the MATCH expression). ``artifact_ids``
    restricts to a specific set of artifacts (used for ``--well`` scoping).
    """
    clauses = ["source_spans_fts MATCH :query"]
    params: dict[str, object] = {"query": query, "limit": limit}
    if kind_filter is not None:
        clauses.append("span_kind = :kind_filter")
        params["kind_filter"] = kind_filter
    if artifact_ids is not None:
        if not artifact_ids:
            return []
        placeholders = ", ".join(f":aid_{i}" for i in range(len(artifact_ids)))
        clauses.append(f"artifact_id IN ({placeholders})")
        for i, aid in enumerate(artifact_ids):
            params[f"aid_{i}"] = aid

    where_sql = " AND ".join(clauses)
    stmt = text(
        f"""
        SELECT span_id, artifact_id, span_kind,
               snippet(source_spans_fts, 0, '[', ']', '...', 12) AS snippet,
               bm25(source_spans_fts) AS rank
        FROM source_spans_fts
        WHERE {where_sql}
        ORDER BY rank
        LIMIT :limit
        """
    )
    try:
        rows = session.execute(stmt, params).all()
    except OperationalError as exc:
        # FTS5 treats (), -, ", and bare AND/OR/NEAR as query operators; an
        # unbalanced or malformed query raises here rather than matching
        # nothing, so surface it as an actionable error instead of a
        # traceback (this is user input, not a framework bug). The caller's
        # session_scope handles the rollback.
        raise InvalidSearchQueryError(
            f"Invalid search query {query!r}: {exc.orig}. "
            'Wrap phrases with special characters in double quotes, e.g. "widget()".'
        ) from exc
    return [
        FtsHit(
            span_id=row.span_id,
            artifact_id=row.artifact_id,
            span_kind=row.span_kind,
            snippet=row.snippet,
            rank=float(row.rank),
        )
        for row in rows
    ]
