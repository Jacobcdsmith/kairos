"""Frozen domain dataclasses mirroring the schema tables.

These are the in-memory shape parsers and services work with; the ORM layer
(``kairos.infrastructure.database.orm``) maps them onto SQLite rows. Keeping
them separate means the domain layer has no SQLAlchemy dependency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from kairos.domain.enums import ArtifactKind, Origin, ParseStatus, SpanKind


@dataclass(frozen=True, slots=True)
class Artifact:
    id: str
    sha256: str
    original_path: str
    kind: ArtifactKind
    size_bytes: int
    ingested_at: datetime
    parser_name: str
    parser_version: str
    parse_status: ParseStatus
    metadata: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass(frozen=True, slots=True)
class SourceSpan:
    id: str
    artifact_id: str
    span_kind: SpanKind
    locator_json: dict[str, object]
    parent_span_id: str | None
    ordinal: int
    text_content: str
    metadata: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass(frozen=True, slots=True)
class Entity:
    id: str
    canonical_name: str
    entity_type: str
    origin: Origin
    metadata: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass(frozen=True, slots=True)
class Mention:
    id: str
    entity_id: str
    source_span_id: str
    surface_form: str
    extraction_rule: str
    confidence: float
    metadata: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass(frozen=True, slots=True)
class Relation:
    id: str
    subject_id: str
    subject_kind: str
    predicate: str
    object_id: str
    object_kind: str
    evidence_span_id: str | None
    origin: Origin
    derivation_rule: str | None
    confidence: float
    metadata: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass(frozen=True, slots=True)
class Note:
    id: str
    target_id: str
    target_kind: str
    body: str
    created_at: datetime
    supersedes_note_id: str | None
    metadata: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass(frozen=True, slots=True)
class CoherenceWell:
    id: str
    name: str
    purpose: str
    created_at: datetime
    metadata: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass(frozen=True, slots=True)
class WellMember:
    id: str
    well_id: str
    target_id: str
    target_kind: str
    added_at: datetime
    note: str | None
    metadata: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass(frozen=True, slots=True)
class Event:
    id: str
    occurred_at: datetime
    event_type: str
    payload: dict[str, object] = field(default_factory=lambda: dict[str, object]())


@dataclass(frozen=True, slots=True)
class Diagnostic:
    """A non-fatal parse problem. Recorded, never used to silently drop data."""

    message: str
    severity: str = "warning"
    locator_json: dict[str, object] | None = None
