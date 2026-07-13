"""Result schemas for ``kairos artifacts`` and ``kairos show``."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from kairos.schemas.provenance import ProvenanceEnvelope


class ArtifactSummary(BaseModel):
    id: str
    sha256: str
    source_path: str
    kind: str
    size_bytes: int
    ingested_at: datetime
    parser_name: str
    parser_version: str
    parse_status: str


class SpanResult(BaseModel):
    span_id: str
    span_kind: str
    ordinal: int
    parent_span_id: str | None
    text_content: str
    provenance: ProvenanceEnvelope


class ArtifactDetail(BaseModel):
    artifact: ArtifactSummary
    spans: list[SpanResult]
