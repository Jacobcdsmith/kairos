"""Result schema for ``kairos logs``."""

from __future__ import annotations

from pydantic import BaseModel

from kairos.schemas.provenance import ProvenanceEnvelope


class LogHit(BaseModel):
    line_number: int
    timestamp: str | None
    level: str | None
    component: str | None
    message: str
    provenance: ProvenanceEnvelope
