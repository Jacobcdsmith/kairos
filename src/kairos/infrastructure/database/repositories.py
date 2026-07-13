"""Thin CRUD and query helpers over the ORM. Services depend on these, not on raw SQLAlchemy."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kairos.infrastructure.database.orm import (
    ArtifactRow,
    CoherenceWellRow,
    EntityRow,
    EventRow,
    MentionRow,
    NoteRow,
    RelationRow,
    SourceSpanRow,
    WellMemberRow,
)

# --- artifacts ---


def insert_artifact(session: Session, row: ArtifactRow) -> None:
    session.add(row)


def get_artifact(session: Session, artifact_id: str) -> ArtifactRow | None:
    return session.get(ArtifactRow, artifact_id)


def get_artifact_by_sha256(session: Session, sha256: str) -> ArtifactRow | None:
    return session.execute(
        select(ArtifactRow).where(ArtifactRow.sha256 == sha256)
    ).scalar_one_or_none()


def list_artifacts(
    session: Session, *, kind: str | None = None, limit: int = 50
) -> list[ArtifactRow]:
    stmt = select(ArtifactRow).order_by(ArtifactRow.ingested_at.desc()).limit(limit)
    if kind is not None:
        stmt = stmt.where(ArtifactRow.kind == kind)
    return list(session.execute(stmt).scalars().all())


# --- source spans ---


def insert_span(session: Session, row: SourceSpanRow) -> None:
    session.add(row)
    session.flush()  # the FTS5 sync trigger fires on INSERT into source_spans


def get_span(session: Session, span_id: str) -> SourceSpanRow | None:
    return session.get(SourceSpanRow, span_id)


def list_spans_for_artifact(session: Session, artifact_id: str) -> list[SourceSpanRow]:
    stmt = (
        select(SourceSpanRow)
        .where(SourceSpanRow.artifact_id == artifact_id)
        .order_by(SourceSpanRow.ordinal)
    )
    return list(session.execute(stmt).scalars().all())


def list_spans_by_kind(session: Session, artifact_id: str, span_kind: str) -> list[SourceSpanRow]:
    stmt = select(SourceSpanRow).where(
        SourceSpanRow.artifact_id == artifact_id, SourceSpanRow.span_kind == span_kind
    )
    return list(session.execute(stmt).scalars().all())


# --- entities / mentions / relations ---


def insert_entity(session: Session, row: EntityRow) -> None:
    session.add(row)


def get_entity(session: Session, entity_id: str) -> EntityRow | None:
    return session.get(EntityRow, entity_id)


def find_entities_by_name(session: Session, canonical_name: str) -> list[EntityRow]:
    stmt = select(EntityRow).where(EntityRow.canonical_name == canonical_name)
    return list(session.execute(stmt).scalars().all())


def find_entities_by_name_ci(session: Session, canonical_name: str) -> list[EntityRow]:
    stmt = select(EntityRow).where(func.lower(EntityRow.canonical_name) == canonical_name.lower())
    return list(session.execute(stmt).scalars().all())


def insert_mention(session: Session, row: MentionRow) -> None:
    session.add(row)


def list_mentions_for_entity(session: Session, entity_id: str) -> list[MentionRow]:
    stmt = select(MentionRow).where(MentionRow.entity_id == entity_id)
    return list(session.execute(stmt).scalars().all())


def list_mentions_for_span(session: Session, source_span_id: str) -> list[MentionRow]:
    stmt = select(MentionRow).where(MentionRow.source_span_id == source_span_id)
    return list(session.execute(stmt).scalars().all())


def insert_relation(session: Session, row: RelationRow) -> None:
    session.add(row)


def list_relations_from(session: Session, subject_id: str) -> list[RelationRow]:
    stmt = select(RelationRow).where(RelationRow.subject_id == subject_id)
    return list(session.execute(stmt).scalars().all())


def list_relations_to(session: Session, object_id: str) -> list[RelationRow]:
    stmt = select(RelationRow).where(RelationRow.object_id == object_id)
    return list(session.execute(stmt).scalars().all())


# --- notes ---


def insert_note(session: Session, row: NoteRow) -> None:
    session.add(row)


def list_notes_for_target(session: Session, target_id: str) -> list[NoteRow]:
    stmt = select(NoteRow).where(NoteRow.target_id == target_id).order_by(NoteRow.created_at)
    return list(session.execute(stmt).scalars().all())


# --- coherence wells ---


def insert_well(session: Session, row: CoherenceWellRow) -> None:
    session.add(row)


def get_well_by_name(session: Session, name: str) -> CoherenceWellRow | None:
    return session.execute(
        select(CoherenceWellRow).where(CoherenceWellRow.name == name)
    ).scalar_one_or_none()


def list_wells(session: Session) -> list[CoherenceWellRow]:
    return list(
        session.execute(select(CoherenceWellRow).order_by(CoherenceWellRow.created_at))
        .scalars()
        .all()
    )


def insert_well_member(session: Session, row: WellMemberRow) -> None:
    session.add(row)


def list_well_members(session: Session, well_id: str) -> list[WellMemberRow]:
    stmt = (
        select(WellMemberRow)
        .where(WellMemberRow.well_id == well_id)
        .order_by(WellMemberRow.added_at)
    )
    return list(session.execute(stmt).scalars().all())


def get_well_member(session: Session, well_id: str, target_id: str) -> WellMemberRow | None:
    return session.execute(
        select(WellMemberRow).where(
            WellMemberRow.well_id == well_id, WellMemberRow.target_id == target_id
        )
    ).scalar_one_or_none()


def get_well_member_by_id(session: Session, member_id: str) -> WellMemberRow | None:
    return session.get(WellMemberRow, member_id)


def delete_well_member(session: Session, row: WellMemberRow) -> None:
    session.delete(row)


# --- events ---


def insert_event(session: Session, row: EventRow) -> None:
    session.add(row)


def list_events(
    session: Session, *, since: datetime | None = None, limit: int = 100
) -> list[EventRow]:
    stmt = select(EventRow).order_by(EventRow.occurred_at.desc()).limit(limit)
    if since is not None:
        stmt = stmt.where(EventRow.occurred_at >= since)
    return list(session.execute(stmt).scalars().all())
