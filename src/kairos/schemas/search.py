"""Result schemas for ``kairos search``."""

from __future__ import annotations

from pydantic import BaseModel

from kairos.schemas.provenance import ProvenanceEnvelope


class SearchHit(BaseModel):
    span_id: str
    snippet: str
    text_content: str
    rank: float
    provenance: ProvenanceEnvelope


class SearchResult(BaseModel):
    query: str
    hits: list[SearchHit]
