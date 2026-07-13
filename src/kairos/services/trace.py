"""``kairos trace`` — evidence-first traversal from a query term or source object.

Seeding (in priority order): an exact artifact id, an exact span id, an
entity whose ``canonical_name`` matches (case-insensitive), or — when none of
those match — the direct FTS5 hits for the query text. From the seed set,
breadth-first traversal follows ``relations`` **and** ``mentions`` in *both*
directions (a relation's object can lead back to its subject; a span can
lead up to the entities it mentions, and an entity down to every span that
mentions it). That bidirectionality is what lets a term with no entity of
its own — say, a word inside a paragraph — climb up to a shared heading
entity and back down to a sibling artifact, crossing document boundaries in
a couple of hops instead of collapsing into a plain search.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from kairos.domain.locators import locator_from_json
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.fts import search_spans
from kairos.infrastructure.database.repositories import (
    find_entities_by_name_ci,
    get_artifact,
    get_entity,
    get_span,
    list_mentions_for_entity,
    list_mentions_for_span,
    list_relations_from,
    list_relations_to,
)
from kairos.schemas.provenance import ProvenanceEnvelope, build_envelope
from kairos.schemas.trace import TraceEdge, TraceNode, TraceResult
from kairos.services.context import RuntimeContext
from kairos.services.wells_scope import well_artifact_ids

_MAX_FTS_SEEDS = 10


@dataclass(frozen=True, slots=True)
class _NodeRef:
    kind: str  # "entity" | "span" | "artifact"
    id: str


def _span_provenance(
    session: Session, ctx: RuntimeContext, span_id: str
) -> ProvenanceEnvelope | None:
    span_row = get_span(session, span_id)
    if span_row is None:
        return None
    artifact_row = get_artifact(session, span_row.artifact_id)
    if artifact_row is None:
        return None
    return build_envelope(
        artifact_id=artifact_row.id,
        source_path=ctx.workspace.relative_path(Path(artifact_row.original_path)),
        artifact_kind=artifact_row.kind,
        locator=locator_from_json(span_row.locator_json),
        parser_name=artifact_row.parser_name,
        parser_version=artifact_row.parser_version,
        layer="extracted",
    )


def _node_label(session: Session, ref: _NodeRef) -> str:
    if ref.kind == "entity":
        entity_row = get_entity(session, ref.id)
        return entity_row.canonical_name if entity_row is not None else ref.id
    if ref.kind == "span":
        span_row = get_span(session, ref.id)
        if span_row is None:
            return ref.id
        text = (
            span_row.text_content.strip().splitlines()[0] if span_row.text_content.strip() else ""
        )
        return text[:80] if text else f"[{span_row.span_kind}]"
    if ref.kind == "artifact":
        artifact_row = get_artifact(session, ref.id)
        return artifact_row.original_path if artifact_row is not None else ref.id
    return ref.id


def _seed_refs(
    session: Session, ctx: RuntimeContext, query: str, well: str | None
) -> list[_NodeRef]:
    if get_artifact(session, query) is not None:
        return [_NodeRef("artifact", query)]
    if get_span(session, query) is not None:
        return [_NodeRef("span", query)]

    entities = find_entities_by_name_ci(session, query)
    if entities:
        return [_NodeRef("entity", e.id) for e in entities]

    artifact_ids = well_artifact_ids(session, well) if well is not None else None
    hits = search_spans(session, query, artifact_ids=artifact_ids, limit=_MAX_FTS_SEEDS)
    return [_NodeRef("span", hit.span_id) for hit in hits]


def trace(
    ctx: RuntimeContext, query: str, *, depth: int = 2, well: str | None = None
) -> TraceResult:
    with session_scope(ctx.session_factory) as session:
        seeds = _seed_refs(session, ctx, query, well)

        visited: set[tuple[str, str]] = set()
        nodes: dict[tuple[str, str], TraceNode] = {}
        edges: list[TraceEdge] = []
        seen_edges: set[tuple[str, str, str, str, str]] = set()

        def add_edge(
            subject_id: str,
            subject_kind: str,
            predicate: str,
            object_id: str,
            object_kind: str,
            layer: str,
            derivation_rule: str | None,
            confidence: float,
            evidence_span_id: str | None,
        ) -> None:
            edge_key = (subject_id, subject_kind, predicate, object_id, object_kind)
            if edge_key in seen_edges:
                return
            seen_edges.add(edge_key)
            evidence = (
                _span_provenance(session, ctx, evidence_span_id) if evidence_span_id else None
            )
            edges.append(
                TraceEdge(
                    subject_id=subject_id,
                    subject_kind=subject_kind,
                    predicate=predicate,
                    object_id=object_id,
                    object_kind=object_kind,
                    layer=layer,
                    derivation_rule=derivation_rule,
                    confidence=confidence,
                    evidence=evidence,
                )
            )

        frontier: list[_NodeRef] = seeds
        for _hop in range(max(depth, 0) + 1):
            next_frontier: list[_NodeRef] = []
            for ref in frontier:
                key = (ref.kind, ref.id)
                if key in visited:
                    continue
                visited.add(key)

                provenance = _span_provenance(session, ctx, ref.id) if ref.kind == "span" else None
                nodes[key] = TraceNode(
                    node_kind=ref.kind,
                    node_id=ref.id,
                    label=_node_label(session, ref),
                    provenance=provenance,
                )

                for rel in list_relations_from(session, ref.id):
                    add_edge(
                        rel.subject_id,
                        rel.subject_kind,
                        rel.predicate,
                        rel.object_id,
                        rel.object_kind,
                        rel.origin,
                        rel.derivation_rule,
                        rel.confidence,
                        rel.evidence_span_id,
                    )
                    next_frontier.append(_NodeRef(rel.object_kind, rel.object_id))

                for rel in list_relations_to(session, ref.id):
                    add_edge(
                        rel.subject_id,
                        rel.subject_kind,
                        rel.predicate,
                        rel.object_id,
                        rel.object_kind,
                        rel.origin,
                        rel.derivation_rule,
                        rel.confidence,
                        rel.evidence_span_id,
                    )
                    next_frontier.append(_NodeRef(rel.subject_kind, rel.subject_id))

                if ref.kind == "entity":
                    for mention in list_mentions_for_entity(session, ref.id):
                        add_edge(
                            ref.id,
                            "entity",
                            "mentioned_in",
                            mention.source_span_id,
                            "span",
                            "extracted",
                            mention.extraction_rule,
                            mention.confidence,
                            mention.source_span_id,
                        )
                        next_frontier.append(_NodeRef("span", mention.source_span_id))

                if ref.kind == "span":
                    for mention in list_mentions_for_span(session, ref.id):
                        add_edge(
                            mention.entity_id,
                            "entity",
                            "mentioned_in",
                            ref.id,
                            "span",
                            "extracted",
                            mention.extraction_rule,
                            mention.confidence,
                            ref.id,
                        )
                        next_frontier.append(_NodeRef("entity", mention.entity_id))

            frontier = [ref for ref in next_frontier if (ref.kind, ref.id) not in visited]

        return TraceResult(query=query, depth=depth, nodes=list(nodes.values()), edges=edges)
