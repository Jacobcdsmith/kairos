"""Result schema for ``kairos ingest``."""

from __future__ import annotations

from pydantic import BaseModel

from kairos.schemas.artifact import ArtifactSummary


class IngestDiagnostic(BaseModel):
    source_path: str
    message: str
    severity: str


class IngestOutcome(BaseModel):
    artifact: ArtifactSummary
    span_count: int
    entity_count: int
    relation_count: int
    diagnostics: list[IngestDiagnostic]
    already_ingested: bool


class IngestReport(BaseModel):
    outcomes: list[IngestOutcome]
