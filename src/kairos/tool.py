"""Agent-facing KAIROS tool adapter.

Every function returns a dict with a ``status`` key ("ok" | "error") —
never raises. Structured results carry ``source_link`` keys where applicable
so agents can render clickable file:// or vscode:// URIs directly.

Usage from execute_code or an agent context::

    from kairos.tool import kairos_ingest, kairos_search, kairos_trace, ...

Standard workflow:

1. kairos_ingest(".", recursive=True)    -- populate the workspace
2. kairos_well_create("task-foo", ...)   -- scope the task
3. kairos_trace("symbol", well="task-foo")  -- find related entities
4. kairos_source_content(artifact_id, locator)  -- get actual bytes
"""

from __future__ import annotations

import os
import urllib.parse
from pathlib import Path
from typing import Any

from kairos.domain.errors import KairosError
from kairos.domain.locators import (
    LineRangeLocator,
    Locator,
    RepoFileLinesLocator,
    locator_from_json,
)
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.repositories import (
    get_artifact,
    get_span,
    list_spans_for_artifact,
)
from kairos.schemas.provenance import ProvenanceEnvelope
from kairos.schemas.trace import TraceResult
from kairos.services.artifacts import list_artifacts as _list_artifacts
from kairos.services.context import RuntimeContext
from kairos.services.ingest import ingest as _ingest
from kairos.services.search import search as _search
from kairos.services.show import show as _show
from kairos.services.trace import trace as _trace
from kairos.services.wells import (
    add_member as _well_add,
    create_well as _well_create,
    list_all_wells as _list_wells,
    remove_member as _well_remove,
    show_well as _well_show,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

_CTX: RuntimeContext | None = None


def _ctx() -> RuntimeContext:
    global _CTX
    if _CTX is None:
        try:
            _CTX = RuntimeContext.open(Path.cwd())
        except Exception as exc:
            raise KairosError(f"No KAIROS workspace found: {exc}") from exc
    return _CTX


def _reset_ctx() -> None:
    global _CTX
    _CTX = None


def _try(fn, **default: Any) -> dict:
    """Wrap a KAIROS service call into a status dict."""
    try:
        return {"status": "ok", **fn()}
    except KairosError as e:
        return {"status": "error", "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": f"{type(e).__name__}: {e}"}


def _source_link_for_envelope(
    envelope: ProvenanceEnvelope, workspace_root: Path
) -> str | None:
    """Build a clickable source link from a provenance envelope."""
    locator = envelope.locator
    source_path = Path(envelope.source_path)
    if source_path.is_absolute():
        abs_path = source_path
    else:
        abs_path = (workspace_root / source_path).resolve()

    if not abs_path.exists():
        return None

    file_uri = abs_path.as_uri()

    # duck-type for line-range locators (Pydantic wraps them as *Model)
    start = getattr(locator, "start_line", None)
    if start is not None:
        end = getattr(locator, "end_line", None)
        return _make_link(file_uri, start, end)

    return file_uri


def _make_link(file_uri: str, start: int, end: int | None = None) -> str:
    """Build file:// and vscode:// links."""
    line_part = f"#{start}" if end is None else f"#{start},{end}"
    vscode_uri = f"vscode://file/{urllib.parse.unquote(file_uri[8:])}:{start}"
    return f"{file_uri}{line_part}  ({vscode_uri})"


def _read_bytes_around_locator(
    abs_path: Path,
    locator: Locator,
    context_lines: int = 3,
) -> dict | None:
    """Read source bytes around a locator and return a snippet dict."""
    if isinstance(locator, LineRangeLocator):
        start, end = locator.start_line, locator.end_line
    elif isinstance(locator, RepoFileLinesLocator):
        start, end = locator.start_line, locator.end_line
    else:
        return None

    try:
        lines = abs_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return None

    ctx_start = max(0, start - context_lines - 1)
    ctx_end = min(len(lines), end + context_lines)

    snippet_lines = []
    for i in range(ctx_start, ctx_end):
        line_no = i + 1
        marker = " >" if start - 1 <= i < end else "  "
        snippet_lines.append(f"{marker} {line_no:4d}|{lines[i]}")

    return {
        "start_line": start,
        "end_line": end,
        "context_before": context_lines,
        "context_after": context_lines,
        "lines": snippet_lines,
        "total_lines_in_file": len(lines),
    }


def _resolve_artifact_path(
    artifact_id: str,
) -> tuple[Path, str] | None:
    """Return (absolute_path, relative_path) for an artifact, or None."""
    ctx = _ctx()
    with session_scope(ctx.session_factory) as session:
        row = get_artifact(session, artifact_id)
        if row is None:
            return None
        abs_path = Path(row.original_path)
        rel_path = ctx.workspace.relative_path(abs_path)
        return abs_path, rel_path


# ---------------------------------------------------------------------------
# public API — each returns a dict with status="ok"|"error"
# ---------------------------------------------------------------------------


def kairos_init(path: str | None = None, name: str | None = None) -> dict:
    """Initialise a KAIROS workspace (like ``kairos init``).

    Args:
        path: Directory to initialise (default: current working directory).
        name: Optional human-friendly name.

    Returns:
        dict with workspace path on success.
    """
    from kairos.infrastructure.filesystem.workspace import init_workspace
    from kairos.infrastructure.database.migrate import upgrade_to_head

    def _run():
        root = Path(path).resolve() if path else Path.cwd().resolve()
        workspace = init_workspace(root, name=name)
        upgrade_to_head(workspace.db_path)
        # force re-resolve on next call
        _reset_ctx()
        return {
            "workspace_path": str(root),
            "db_path": str(workspace.db_path),
            "name": workspace.name,
        }

    return _try(_run)


def kairos_ingest(path: str = ".", recursive: bool = True) -> dict:
    """Ingest files into the workspace.

    Args:
        path: File or directory path (relative or absolute).
        recursive: Whether to recurse into directories.

    Returns:
        dict with outcomes list (each: id, source_path, kind, status, spans,
        already_ingested, diagnostics).
    """
    ctx = _ctx()

    def _run():
        report = _ingest(ctx, Path(path), recursive=recursive)
        outcomes = []
        for o in report.outcomes:
            artifacts = _list_artifacts(ctx)
            source_link = None
            for a in artifacts:
                if a.id == o.artifact.id:
                    abs_path = Path.cwd() / a.source_path if not Path(a.source_path).is_absolute() else Path(a.source_path)
                    source_link = abs_path.resolve().as_uri()
                    break
            outcomes.append(
                {
                    "id": o.artifact.id,
                    "source_path": o.artifact.source_path,
                    "kind": o.artifact.kind,
                    "parse_status": o.artifact.parse_status,
                    "span_count": o.span_count,
                    "entity_count": o.entity_count,
                    "relation_count": o.relation_count,
                    "already_ingested": o.already_ingested,
                    "diagnostics": [
                        {"message": d.message, "severity": d.severity}
                        for d in o.diagnostics
                    ],
                    "source_link": source_link,
                }
            )
        return {
            "total": len(outcomes),
            "new": sum(1 for o in report.outcomes if not o.already_ingested),
            "already_ingested": sum(1 for o in report.outcomes if o.already_ingested),
            "outcomes": outcomes,
        }

    return _try(_run)


def kairos_search(query: str, limit: int = 20, well: str | None = None) -> dict:
    """Full-text search with provenance envelopes.

    Args:
        query: Search text.
        limit: Max hits.
        well: Optional coherence well name to scope the search.

    Returns:
        dict with hits list (each: span_id, snippet, score, source_path,
        locator_str, source_link, text_content).
    """
    ctx = _ctx()

    def _run():
        result = _search(ctx, query, well=well)
        hits = []
        ws_root = ctx.workspace.root
        for h in result.hits[:limit]:
            source_link = _source_link_for_envelope(h.provenance, ws_root)
            snippet = h.snippet[:200] if h.snippet else ""
            hits.append(
                {
                    "span_id": h.span_id,
                    "snippet": snippet,
                    "score": h.rank,
                    "source_path": h.provenance.source_path,
                    "artifact_id": h.provenance.artifact_id,
                    "artifact_kind": h.provenance.artifact_kind,
                    "locator_str": h.provenance.locator_str,
                    "locator": h.provenance.locator.model_dump(),
                    "source_link": source_link,
                    "parser_name": h.provenance.parser_name,
                    "parser_version": h.provenance.parser_version,
                    "layer": h.provenance.layer,
                }
            )
        return {"query": query, "total_hits": len(result.hits), "hits": hits}

    return _try(_run)


def kairos_trace(
    term: str, depth: int = 2, well: str | None = None
) -> dict:
    """Bidirectional entity trace with provenance on every edge.

    Args:
        term: Entity name, artifact ID, span ID, or free-text fallback.
        depth: BFS traversal depth.
        well: Optional coherence well scope.

    Returns:
        dict with nodes (each: kind, id, label, source_link) and edges.
    """
    ctx = _ctx()

    def _run():
        result: TraceResult = _trace(ctx, term, depth=depth, well=well)
        ws_root = ctx.workspace.root
        nodes_out = []
        for n in result.nodes:
            source_link = None
            if n.provenance is not None:
                source_link = _source_link_for_envelope(n.provenance, ws_root)
            nodes_out.append(
                {
                    "kind": n.node_kind,
                    "id": n.node_id,
                    "label": n.label,
                    "source_link": source_link,
                    "provenance": (
                        {
                            "source_path": n.provenance.source_path,
                            "locator_str": n.provenance.locator_str,
                            "artifact_kind": n.provenance.artifact_kind,
                        }
                        if n.provenance
                        else None
                    ),
                }
            )
        edges_out = []
        for e in result.edges:
            edges_out.append(
                {
                    "subject_id": e.subject_id,
                    "subject_kind": e.subject_kind,
                    "predicate": e.predicate,
                    "object_id": e.object_id,
                    "object_kind": e.object_kind,
                    "layer": e.layer,
                    "derivation_rule": e.derivation_rule,
                    "confidence": e.confidence,
                }
            )
        return {
            "query": term,
            "depth": depth,
            "node_count": len(nodes_out),
            "edge_count": len(edges_out),
            "nodes": nodes_out,
            "edges": edges_out,
        }

    return _try(_run)


def kairos_show(artifact_id: str) -> dict:
    """Show full artifact detail with all spans and provenance.

    Args:
        artifact_id: Artifact UUID.

    Returns:
        dict with artifact summary and spans list.
    """
    ctx = _ctx()

    def _run():
        detail = _show(ctx, artifact_id)
        ws_root = ctx.workspace.root
        spans = []
        for s in detail.spans:
            source_link = _source_link_for_envelope(s.provenance, ws_root)
            spans.append(
                {
                    "span_id": s.span_id,
                    "span_kind": s.span_kind,
                    "ordinal": s.ordinal,
                    "text_content": s.text_content[:500],
                    "locator_str": s.provenance.locator_str,
                    "source_link": source_link,
                }
            )
        return {
            "artifact": {
                "id": detail.artifact.id,
                "source_path": detail.artifact.source_path,
                "kind": detail.artifact.kind,
                "parser_name": detail.artifact.parser_name,
                "parser_version": detail.artifact.parser_version,
                "parse_status": detail.artifact.parse_status,
                "size_bytes": detail.artifact.size_bytes,
                "sha256": detail.artifact.sha256,
            },
            "spans": spans,
        }

    return _try(_run)


def kairos_source_content(
    artifact_id: str,
    context_lines: int = 3,
) -> dict:
    """Read actual source bytes around each locatable span.

    Args:
        artifact_id: Artifact UUID to read.
        context_lines: Lines of context before/after each span.

    Returns:
        dict with file_path and snippets per span.
    """
    ctx = _ctx()

    def _run():
        resolved = _resolve_artifact_path(artifact_id)
        if resolved is None:
            raise KairosError(f"Artifact not found: {artifact_id}")
        abs_path, rel_path = resolved

        with session_scope(ctx.session_factory) as session:
            span_rows = list_spans_for_artifact(session, artifact_id)

        payload = {
            "artifact_id": artifact_id,
            "source_path": str(rel_path),
            "file_path": str(abs_path),
            "source_link": abs_path.as_uri(),
            "exists": abs_path.exists(),
            "spans": [],
        }

        if not abs_path.exists():
            return payload

        for sr in span_rows:
            locator = locator_from_json(sr.locator_json)
            snippet = _read_bytes_around_locator(abs_path, locator, context_lines)
            if snippet is not None:
                payload["spans"].append(
                    {
                        "span_id": sr.id,
                        "span_kind": sr.span_kind,
                        "snippet": snippet,
                    }
                )

        return payload

    return _try(_run)


def kairos_source_link(artifact_id: str, locator_str: str | None = None) -> dict:
    """Resolve an artifact + optional locator to clickable source links.

    Args:
        artifact_id: Artifact UUID.
        locator_str: Optional locator string (e.g. "lines:42-87").
                     Uses the artifact's first span if omitted.

    Returns:
        dict with file:// and vscode:// links.
    """
    ctx = _ctx()

    def _run():
        resolved = _resolve_artifact_path(artifact_id)
        if resolved is None:
            raise KairosError(f"Artifact not found: {artifact_id}")
        abs_path, rel_path = resolved

        if locator_str:
            from kairos.domain.locators import parse_locator_str

            locator = parse_locator_str(locator_str)
        else:
            with session_scope(ctx.session_factory) as session:
                spans = list_spans_for_artifact(session, artifact_id)
            if not spans:
                # fallback: whole file
                file_uri = abs_path.as_uri()
                return {"source_link": file_uri}
            locator = locator_from_json(spans[0].locator_json)

        file_uri = abs_path.as_uri()
        source_link = _make_link(file_uri, locator.start_line, locator.end_line) if isinstance(locator, (LineRangeLocator, RepoFileLinesLocator)) else file_uri

        return {
            "artifact_id": artifact_id,
            "source_path": str(rel_path),
            "source_link": source_link,
            "file_uri": file_uri,
            "locator_str": locator_str or "",
        }

    return _try(_run)


def kairos_artifacts(kind: str | None = None) -> dict:
    """List artifacts in the workspace.

    Args:
        kind: Optional filter (e.g. "markdown", "python", "json").

    Returns:
        dict with artifacts list.
    """
    ctx = _ctx()

    def _run():
        items = _list_artifacts(ctx, kind=kind)
        return {
            "total": len(items),
            "artifacts": [
                {
                    "id": a.id,
                    "source_path": a.source_path,
                    "kind": a.kind,
                    "size_bytes": a.size_bytes,
                    "parser_name": a.parser_name,
                    "parse_status": a.parse_status,
                    "ingested_at": a.ingested_at.isoformat(),
                }
                for a in items
            ],
        }

    return _try(_run)


def kairos_well_create(name: str, purpose: str = "") -> dict:
    """Create a coherence well to scope a working set.

    Args:
        name: Well name (unique).
        purpose: Human-readable purpose.

    Returns:
        dict with well details.
    """
    ctx = _ctx()

    def _run():
        well = _well_create(ctx, name, purpose)
        return {
            "id": well.id,
            "name": well.name,
            "purpose": well.purpose,
            "member_count": well.member_count,
        }

    return _try(_run)


def kairos_well_add(well_name: str, target_id: str, note: str | None = None) -> dict:
    """Add an artifact or span to a coherence well.

    Args:
        well_name: Existing well name.
        target_id: Artifact or span UUID.
        note: Optional note.

    Returns:
        dict with member details.
    """
    ctx = _ctx()

    def _run():
        member = _well_add(ctx, well_name, target_id, note=note)
        return {
            "id": member.id,
            "well_id": member.well_id,
            "target_id": member.target_id,
            "target_kind": member.target_kind,
            "note": member.note,
        }

    return _try(_run)


def kairos_well_show(well_name: str) -> dict:
    """Show a coherence well's contents.

    Args:
        well_name: Well name.

    Returns:
        dict with well + members list.
    """
    ctx = _ctx()

    def _run():
        detail = _well_show(ctx, well_name)
        return {
            "id": detail.well.id,
            "name": detail.well.name,
            "purpose": detail.well.purpose,
            "member_count": detail.well.member_count,
            "members": [
                {
                    "id": m.id,
                    "target_id": m.target_id,
                    "target_kind": m.target_kind,
                    "note": m.note,
                }
                for m in detail.members
            ],
        }

    return _try(_run)


def kairos_well_list() -> dict:
    """List all coherence wells.

    Returns:
        dict with wells list.
    """
    ctx = _ctx()

    def _run():
        wells = _list_wells(ctx)
        return {
            "total": len(wells),
            "wells": [
                {
                    "id": w.id,
                    "name": w.name,
                    "purpose": w.purpose,
                    "member_count": w.member_count,
                }
                for w in wells
            ],
        }

    return _try(_run)


def kairos_well_remove(well_name: str, member_id: str) -> dict:
    """Remove a member from a coherence well.

    Args:
        well_name: Well name.
        member_id: Member UUID to remove.

    Returns:
        dict confirming removal.
    """
    ctx = _ctx()

    def _run():
        _well_remove(ctx, well_name, member_id)
        return {"well_name": well_name, "removed_member_id": member_id}

    return _try(_run)


def kairos_status() -> dict:
    """Check KAIROS workspace status.

    Returns:
        dict with workspace info, artifact/entity counts, and health.
    """
    ctx = _ctx()

    def _run():
        from sqlalchemy import text as _text

        import json as _json
        from kairos.infrastructure.database.engine import fts5_is_available

        # read config for name/schema_version
        _ws_cfg = {}
        try:
            _ws_cfg = _json.loads(ctx.workspace.config_path.read_text(encoding="utf-8"))
        except Exception:
            pass

        with session_scope(ctx.session_factory) as session:
            artifacts = session.execute(
                _text("SELECT COUNT(*) FROM artifacts")
            ).scalar() or 0
            entities = session.execute(
                _text("SELECT COUNT(*) FROM entities")
            ).scalar() or 0
            relations = session.execute(
                _text("SELECT COUNT(*) FROM relations")
            ).scalar() or 0
            spans = session.execute(
                _text("SELECT COUNT(*) FROM source_spans")
            ).scalar() or 0
            wells = session.execute(
                _text("SELECT COUNT(*) FROM coherence_wells")
            ).scalar() or 0

        return {
            "workspace": {
                "root": str(ctx.workspace.root),
                "name": _ws_cfg.get("name", ""),
                "schema_version": _ws_cfg.get("schema_version", ""),
            },
            "counts": {
                "artifacts": artifacts,
                "spans": spans,
                "entities": entities,
                "relations": relations,
                "wells": wells,
            },
            "health": {
                "fts5_available": fts5_is_available(),
            },
        }

    return _try(_run)
