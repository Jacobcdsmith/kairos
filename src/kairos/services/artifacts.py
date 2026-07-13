"""``kairos artifacts`` — list ingested artifacts."""

from __future__ import annotations

from pathlib import Path

from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.repositories import list_artifacts as repo_list_artifacts
from kairos.schemas.artifact import ArtifactSummary
from kairos.services.context import RuntimeContext


def list_artifacts(
    ctx: RuntimeContext, *, kind: str | None = None, limit: int = 50
) -> list[ArtifactSummary]:
    with session_scope(ctx.session_factory) as session:
        rows = repo_list_artifacts(session, kind=kind, limit=limit)
        return [
            ArtifactSummary(
                id=row.id,
                sha256=row.sha256,
                source_path=ctx.workspace.relative_path(Path(row.original_path)),
                kind=row.kind,
                size_bytes=row.size_bytes,
                ingested_at=row.ingested_at,
                parser_name=row.parser_name,
                parser_version=row.parser_version,
                parse_status=row.parse_status,
            )
            for row in rows
        ]
