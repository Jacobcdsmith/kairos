"""SQLAlchemy 2.x ORM models, mapped 1:1 onto the schema. Column names are verbatim.

``source_spans_fts`` (FTS5) is deliberately **not** modeled here — it is a
virtual table with sync triggers, created as raw DDL in the migration and
queried via Core ``text()`` (see ``kairos.infrastructure.database.fts``).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ArtifactRow(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    sha256: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    original_path: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String, index=True, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    parser_name: Mapped[str] = mapped_column(String, nullable=False)
    parser_version: Mapped[str] = mapped_column(String, nullable=False)
    parse_status: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class SourceSpanRow(Base):
    __tablename__ = "source_spans"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    artifact_id: Mapped[str] = mapped_column(
        String, ForeignKey("artifacts.id"), index=True, nullable=False
    )
    span_kind: Mapped[str] = mapped_column(String, nullable=False)
    locator_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    parent_span_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("source_spans.id"), index=True, nullable=True
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text_content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class EntityRow(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    canonical_name: Mapped[str] = mapped_column(String, index=True, nullable=False)
    entity_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    origin: Mapped[str] = mapped_column(String, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class MentionRow(Base):
    __tablename__ = "mentions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    entity_id: Mapped[str] = mapped_column(
        String, ForeignKey("entities.id"), index=True, nullable=False
    )
    source_span_id: Mapped[str] = mapped_column(
        String, ForeignKey("source_spans.id"), index=True, nullable=False
    )
    surface_form: Mapped[str] = mapped_column(String, nullable=False)
    extraction_rule: Mapped[str] = mapped_column(String, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class RelationRow(Base):
    __tablename__ = "relations"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    subject_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    subject_kind: Mapped[str] = mapped_column(String, nullable=False)
    predicate: Mapped[str] = mapped_column(String, index=True, nullable=False)
    object_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    object_kind: Mapped[str] = mapped_column(String, nullable=False)
    evidence_span_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("source_spans.id"), nullable=True
    )
    origin: Mapped[str] = mapped_column(String, nullable=False)
    derivation_rule: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class NoteRow(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    target_id: Mapped[str] = mapped_column(String, index=True, nullable=False)
    target_kind: Mapped[str] = mapped_column(String, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    supersedes_note_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("notes.id"), nullable=True
    )
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class CoherenceWellRow(Base):
    __tablename__ = "coherence_wells"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class WellMemberRow(Base):
    __tablename__ = "well_members"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    well_id: Mapped[str] = mapped_column(
        String, ForeignKey("coherence_wells.id"), index=True, nullable=False
    )
    target_id: Mapped[str] = mapped_column(String, nullable=False)
    target_kind: Mapped[str] = mapped_column(String, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)


class EventRow(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String, index=True, nullable=False)
    payload_json: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False, default=dict)
