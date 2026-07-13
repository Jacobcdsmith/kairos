"""Ingest service: hash, store, parse, persist spans/entities/relations, and
record an append-only event. Malformed content is never silently dropped —
diagnostics ride along on the artifact's ``metadata_json`` and as their own
event.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.orm import Session

from kairos.domain.errors import NoParserAvailableError, SourcePathNotFoundError
from kairos.domain.ids import new_id
from kairos.domain.models import Entity
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.orm import (
    ArtifactRow,
    EntityRow,
    MentionRow,
    RelationRow,
    SourceSpanRow,
)
from kairos.infrastructure.database.repositories import (
    find_entities_by_name,
    get_artifact_by_sha256,
    insert_artifact,
    insert_entity,
    insert_mention,
    insert_relation,
    insert_span,
)
from kairos.infrastructure.git.metadata import read_git_metadata
from kairos.schemas.artifact import ArtifactSummary
from kairos.schemas.ingest import IngestDiagnostic, IngestOutcome, IngestReport
from kairos.services.context import RuntimeContext
from kairos.services.events import append_event

_IGNORED_DIR_NAMES = {".git", ".kairos", "__pycache__", ".venv", "venv"}


def _walk_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if any(part in _IGNORED_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        files.append(path)
    return files


def _artifact_summary(row: ArtifactRow, source_path: str) -> ArtifactSummary:
    return ArtifactSummary(
        id=row.id,
        sha256=row.sha256,
        source_path=source_path,
        kind=row.kind,
        size_bytes=row.size_bytes,
        ingested_at=row.ingested_at,
        parser_name=row.parser_name,
        parser_version=row.parser_version,
        parse_status=row.parse_status,
    )


def _ingest_one(
    ctx: RuntimeContext,
    session: Session,
    file_path: Path,
    git_metadata: dict[str, object] | None,
) -> IngestOutcome | None:
    stored = ctx.content_store.put(file_path)
    source_path = ctx.workspace.relative_path(file_path)

    existing = get_artifact_by_sha256(session, stored.sha256)
    if existing is not None:
        return IngestOutcome(
            artifact=_artifact_summary(existing, source_path),
            span_count=0,
            entity_count=0,
            relation_count=0,
            diagnostics=[],
            already_ingested=True,
        )

    try:
        parser = ctx.parser_registry.resolve(file_path)
    except NoParserAvailableError:
        # Unrecognized file kind (e.g. a binary asset) — not a malformed known
        # kind, so it's skipped rather than recorded as a parse failure.
        return None

    artifact_id = new_id()
    parse_result = parser.parse(file_path, artifact_id)

    metadata: dict[str, object] = dict(parse_result.artifact_metadata)
    if git_metadata is not None:
        metadata["git"] = git_metadata
    if parse_result.diagnostics:
        metadata["diagnostics"] = [
            {"message": d.message, "severity": d.severity, "locator_json": d.locator_json}
            for d in parse_result.diagnostics
        ]

    ingested_at = datetime.now(UTC)
    artifact_row = ArtifactRow(
        id=artifact_id,
        sha256=stored.sha256,
        original_path=str(file_path.resolve()),
        kind=parser.kind.value,
        size_bytes=stored.size_bytes,
        ingested_at=ingested_at,
        parser_name=parser.parser_name,
        parser_version=parser.parser_version,
        parse_status=parse_result.parse_status.value,
        metadata_json=metadata,
    )
    insert_artifact(session, artifact_row)

    # Reconcile entities across artifacts: same (canonical_name, entity_type)
    # resolves to the same row, which is what lets `trace` cross documents.
    entity_id_map: dict[str, str] = {}
    for entity in parse_result.entities:
        final_id = _reconcile_entity(session, entity)
        entity_id_map[entity.id] = final_id

    for span in parse_result.spans:
        insert_span(
            session,
            SourceSpanRow(
                id=span.id,
                artifact_id=span.artifact_id,
                span_kind=span.span_kind.value,
                locator_json=span.locator_json,
                parent_span_id=span.parent_span_id,
                ordinal=span.ordinal,
                text_content=span.text_content,
                metadata_json=span.metadata,
            ),
        )

    for mention in parse_result.mentions:
        insert_mention(
            session,
            MentionRow(
                id=mention.id,
                entity_id=entity_id_map.get(mention.entity_id, mention.entity_id),
                source_span_id=mention.source_span_id,
                surface_form=mention.surface_form,
                extraction_rule=mention.extraction_rule,
                confidence=mention.confidence,
                metadata_json=mention.metadata,
            ),
        )

    for relation in parse_result.relations:
        subject_id = (
            entity_id_map.get(relation.subject_id, relation.subject_id)
            if relation.subject_kind == "entity"
            else relation.subject_id
        )
        object_id = (
            entity_id_map.get(relation.object_id, relation.object_id)
            if relation.object_kind == "entity"
            else relation.object_id
        )
        insert_relation(
            session,
            RelationRow(
                id=relation.id,
                subject_id=subject_id,
                subject_kind=relation.subject_kind,
                predicate=relation.predicate,
                object_id=object_id,
                object_kind=relation.object_kind,
                evidence_span_id=relation.evidence_span_id,
                origin=relation.origin.value,
                derivation_rule=relation.derivation_rule,
                confidence=relation.confidence,
                metadata_json=relation.metadata,
            ),
        )

    session.flush()

    diagnostics = [
        IngestDiagnostic(source_path=source_path, message=d.message, severity=d.severity)
        for d in parse_result.diagnostics
    ]

    return IngestOutcome(
        artifact=_artifact_summary(artifact_row, source_path),
        span_count=len(parse_result.spans),
        entity_count=len(parse_result.entities),
        relation_count=len(parse_result.relations),
        diagnostics=diagnostics,
        already_ingested=False,
    )


def _reconcile_entity(session: Session, entity: Entity) -> str:
    candidates = find_entities_by_name(session, entity.canonical_name)
    for candidate in candidates:
        if candidate.entity_type == entity.entity_type:
            return candidate.id
    insert_entity(
        session,
        EntityRow(
            id=entity.id,
            canonical_name=entity.canonical_name,
            entity_type=entity.entity_type,
            origin=entity.origin.value,
            metadata_json=entity.metadata,
        ),
    )
    return entity.id


def ingest(ctx: RuntimeContext, path: Path, *, recursive: bool = False) -> IngestReport:
    if not path.exists():
        raise SourcePathNotFoundError(f"Source path does not exist: {path}")

    if path.is_dir():
        if not recursive:
            raise SourcePathNotFoundError(
                f"{path} is a directory. Pass --recursive to ingest a directory tree."
            )
        files = _walk_files(path)
    else:
        files = [path]

    git_meta_obj = read_git_metadata(path)
    git_metadata: dict[str, object] | None = (
        {
            "branch": git_meta_obj.branch,
            "commit": git_meta_obj.commit,
            "remote_url": git_meta_obj.remote_url,
        }
        if git_meta_obj is not None
        else None
    )

    outcomes: list[IngestOutcome] = []
    with session_scope(ctx.session_factory) as session:
        for file_path in files:
            outcome = _ingest_one(ctx, session, file_path, git_metadata)
            if outcome is not None:
                outcomes.append(outcome)
        append_event(
            session,
            ctx.workspace,
            "ingest.run",
            {
                "path": ctx.workspace.relative_path(path),
                "recursive": recursive,
                "artifact_count": len(outcomes),
            },
        )

    return IngestReport(outcomes=outcomes)
