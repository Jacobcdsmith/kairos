"""Result schemas for ``kairos trace``: an evidence-first traversal graph."""

from __future__ import annotations

from pydantic import BaseModel

from kairos.schemas.provenance import ProvenanceEnvelope


class TraceNode(BaseModel):
    node_kind: str  # "entity" | "span" | "artifact"
    node_id: str
    label: str
    provenance: ProvenanceEnvelope | None = None


class TraceEdge(BaseModel):
    subject_id: str
    subject_kind: str
    predicate: str
    object_id: str
    object_kind: str
    layer: str  # "extracted" (mentions) | "derived" (relations)
    derivation_rule: str | None
    confidence: float
    evidence: ProvenanceEnvelope | None = None


class TraceResult(BaseModel):
    query: str
    depth: int
    nodes: list[TraceNode]
    edges: list[TraceEdge]
