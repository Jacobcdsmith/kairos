"""The Evidence pane: "what exactly supports the selected item?" Always
renders the full citation envelope for ``state.selection`` — never a
truncated or summarized one — plus the source excerpt and, for relations,
an explicit statement that the edge is a deterministic rule match, not a
semantic-similarity claim.
"""

from __future__ import annotations

from rich.markup import escape
from textual.widgets import Static

from kairos.cli.citation import provenance_lines
from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary
from kairos.schemas.config import ConfigSymbolResult
from kairos.schemas.doctor import DoctorReport
from kairos.schemas.logs import LogHit
from kairos.schemas.note import NoteResult
from kairos.schemas.provenance import ProvenanceEnvelope
from kairos.schemas.search import SearchResult
from kairos.schemas.trace import TraceResult
from kairos.schemas.well import WellDetail, WellSummary
from kairos.tui.state import TuiState, as_list_of

_NOT_SIMILARITY_NOTICE = (
    "This is an explicit deterministic relation.\nIt is not a semantic similarity claim."
)


def _artifact_summary_lines(a: ArtifactSummary) -> str:
    return (
        f"artifact_id: {a.id}\n"
        f"path: {escape(a.source_path)}\n"
        f"kind: {a.kind}\n"
        f"parser: {a.parser_name} v{a.parser_version}\n"
        f"parse_status: {a.parse_status}\n"
        f"sha256: {a.sha256}\n"
        f"ingested_at: {a.ingested_at.isoformat(timespec='seconds')}"
    )


class EvidencePane(Static):
    # Static widgets aren't focusable by default; Evidence is one of the
    # four panes Tab/Shift+Tab must be able to cycle focus into.
    can_focus = True

    def refresh_from_state(self, state: TuiState) -> None:
        self.update(_render(state))


def _render(state: TuiState) -> str:
    selection = state.selection
    result = state.last_result

    if isinstance(result, ConfigSymbolResult):
        # A single-record result: always shown, no selection required.
        body = provenance_lines(result.provenance)
        extra = (
            f"prompt: {result.prompt or '(none)'}\n"
            f"choices: {', '.join(result.choices) or '(none)'}\n"
            f"children: {', '.join(result.children) or '(none)'}"
        )
        return f"{extra}\n\n{body}"

    if isinstance(result, DoctorReport):
        check = next((c for c in result.checks if c.name == selection.id), None)
        if check is None:
            return "Select a check to see its full detail."
        status = "PASS" if check.ok else "FAIL"
        return f"check: {check.name}\nstatus: {status}\ndetail: {escape(check.detail)}"

    if selection.kind == "none" or selection.id is None:
        return "Nothing selected.\nPress Enter on an item in Explorer to inspect it."

    if (artifacts := as_list_of(result, ArtifactSummary)) is not None:
        artifact = next((a for a in artifacts if a.id == selection.id), None)
        if artifact is None:
            return "Selected item is not in the current result set."
        return _artifact_summary_lines(artifact)

    if isinstance(result, SearchResult):
        hit = next((h for h in result.hits if h.span_id == selection.id), None)
        if hit is None:
            return "Selected item is not in the current result set."
        return f"{provenance_lines(hit.provenance)}\n\n{escape(hit.text_content)}"

    if isinstance(result, ArtifactDetail):
        if selection.id == result.artifact.id:
            return _artifact_summary_lines(result.artifact)
        span = next((s for s in result.spans if s.span_id == selection.id), None)
        if span is None:
            return "Selected item is not in the current result set."
        return f"{provenance_lines(span.provenance)}\n\n{escape(span.text_content)}"

    if isinstance(result, TraceResult):
        node = next((n for n in result.nodes if n.node_id == selection.id), None)
        if node is None:
            return "Selected item is not in the current result set."
        lines = [f"label: {escape(node.label)}", f"kind: {node.node_kind}"]
        if node.provenance is not None:
            lines.append(provenance_lines(node.provenance))
        touching = [e for e in result.edges if selection.id in (e.subject_id, e.object_id)]
        if touching:
            lines.append("")
            lines.append("relations:")
            for edge in touching:
                lines.append(
                    f"  {edge.subject_id[:8]} --{edge.predicate}--> {edge.object_id[:8]}  "
                    f"({edge.layer}, rule={edge.derivation_rule or 'n/a'})"
                )
            if any(e.layer == "derived" for e in touching):
                lines.append("")
                lines.append(_NOT_SIMILARITY_NOTICE)
        return "\n".join(lines)

    if (log_hits := as_list_of(result, LogHit)) is not None:
        hit = next((h for h in log_hits if h.provenance.locator_str == selection.id), None)
        if hit is None:
            return "Selected item is not in the current result set."
        return f"{provenance_lines(hit.provenance)}\n\n{escape(hit.message)}"

    if (wells := as_list_of(result, WellSummary)) is not None:
        well = next((w for w in wells if w.name == selection.id), None)
        if well is None:
            return "Selected item is not in the current result set."
        created_at = well.created_at.isoformat(timespec="seconds")
        return (
            f"well: {well.name}\npurpose: {escape(well.purpose)}\n"
            f"members: {well.member_count}\ncreated_at: {created_at}"
        )

    if isinstance(result, WellDetail):
        member = next((m for m in result.members if m.target_id == selection.id), None)
        if member is None:
            return "Selected item is not in the current result set."
        return (
            f"well: {result.well.name}\ntarget_kind: {member.target_kind}\n"
            f"target_id: {member.target_id}\nnote: {escape(member.note or '(none)')}\n"
            f"added_at: {member.added_at.isoformat(timespec='seconds')}"
        )

    if (notes := as_list_of(result, NoteResult)) is not None:
        note = next((n for n in notes if n.id == selection.id), None)
        if note is None:
            return "Selected item is not in the current result set."
        return (
            f"note_id: {note.id}\ntarget_id: {note.target_id} ({note.target_kind})\n"
            f"created_at: {note.created_at.isoformat(timespec='seconds')}\n\n{escape(note.body)}"
        )

    return "Nothing to show for the current selection."


def _envelope_and_excerpt(state: TuiState) -> tuple[ProvenanceEnvelope | None, str | None]:
    """The raw (unescaped) citation envelope and source excerpt for the
    current selection, if any — the shared lookup behind ``citation_text``
    and ``excerpt_text`` (the payloads for the ``c``/``y`` keybindings).
    Deliberately separate from ``_render``, which returns an already
    Rich-escaped display string unsuitable for clipboard/plain-text copy.
    """
    selection = state.selection
    result = state.last_result

    if isinstance(result, ConfigSymbolResult):
        return result.provenance, None
    if selection.kind == "none" or selection.id is None:
        return None, None
    if isinstance(result, SearchResult):
        hit = next((h for h in result.hits if h.span_id == selection.id), None)
        return (hit.provenance, hit.text_content) if hit is not None else (None, None)
    if isinstance(result, ArtifactDetail):
        span = next((s for s in result.spans if s.span_id == selection.id), None)
        return (span.provenance, span.text_content) if span is not None else (None, None)
    if (log_hits := as_list_of(result, LogHit)) is not None:
        hit = next((h for h in log_hits if h.provenance.locator_str == selection.id), None)
        return (hit.provenance, hit.message) if hit is not None else (None, None)
    if (notes := as_list_of(result, NoteResult)) is not None:
        note = next((n for n in notes if n.id == selection.id), None)
        return (None, note.body) if note is not None else (None, None)
    if isinstance(result, TraceResult):
        node = next((n for n in result.nodes if n.node_id == selection.id), None)
        return (node.provenance, node.label) if node is not None else (None, None)
    return None, None


def citation_text(state: TuiState) -> str | None:
    """Plain-text citation for the ``c`` keybinding, or ``None`` if the
    current selection has no citation to copy.
    """
    envelope, _ = _envelope_and_excerpt(state)
    return provenance_lines(envelope) if envelope is not None else None


def excerpt_text(state: TuiState) -> str | None:
    """Plain-text source excerpt for the ``y`` keybinding, or ``None`` if
    the current selection has no excerpt to copy.
    """
    _, excerpt = _envelope_and_excerpt(state)
    return excerpt
