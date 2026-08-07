"""The Evidence pane: "what exactly supports the selected item?" Always
renders the full citation envelope for ``state.selection`` — never a
truncated or summarized one — plus the source excerpt and, for relations,
an explicit statement that the edge is a deterministic rule match, not a
semantic-similarity claim.
"""

from __future__ import annotations

from rich.markup import escape
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
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
    "\u25c6 This is an explicit deterministic relation.\n  It is not a semantic similarity claim."
)

_LAYER_GLYPH = {
    "raw": "\u25cb",
    "extracted": "\u25cf",
    "derived": "\u25c7",
    "user": "\u270e",
}


def _artifact_summary_lines(a: ArtifactSummary) -> str:
    return (
        f"\u25a1 artifact\n"
        f"  id: {a.id}\n"
        f"  path: {escape(a.source_path)}\n"
        f"  kind: {a.kind}\n"
        f"  parser: {a.parser_name} v{a.parser_version}\n"
        f"  status: {a.parse_status}\n"
        f"  sha256: {a.sha256[:16]}...\n"
        f"  ingested: {a.ingested_at.isoformat(timespec='seconds')}"
    )


class EvidencePane(VerticalScroll):
    """A ``VerticalScroll`` wrapping a single inner ``Static`` — not a bare
    ``Static`` directly, because a leaf widget with no children is never
    ``is_scrollable`` in Textual (see ``Widget.is_scrollable``), so its
    built-in ``action_scroll_*``/``action_page_*`` bindings would silently
    no-op regardless of content overflow. Wrapping in a real scrollable
    container makes ↑/↓ and Page Up/Down actually move the viewport.
    ``renderable`` is proxied through so callers (and existing tests) that
    read the pane's text can keep treating it like a ``Static``.
    """

    can_focus = True

    # `action_scroll_up`/`_down`/`_home`/`_end` and `action_page_up`/`_down`
    # are built into `Widget` already (see textual.widget) — this only wires
    # the keys, since a plain container doesn't bind them by default the way
    # ListView binds arrow keys for its own highlight-driven scrolling.
    BINDINGS = [
        Binding("up", "scroll_up", "Scroll up", show=False),
        Binding("down", "scroll_down", "Scroll down", show=False),
        Binding("pageup", "page_up", "Page up", show=False),
        Binding("pagedown", "page_down", "Page down", show=False),
        Binding("home", "scroll_home", "Top", show=False),
        Binding("end", "scroll_end", "Bottom", show=False),
    ]

    def compose(self) -> ComposeResult:
        yield Static("", id="evidence-content")

    @property
    def renderable(self) -> object:
        return self.query_one("#evidence-content", Static).renderable

    def refresh_from_state(self, state: TuiState) -> None:
        self.query_one("#evidence-content", Static).update(_render(state))
        # Deferred so the scroll reset happens after the layout pass that
        # recomputes virtual_size for the new content — resetting before
        # that pass runs against a stale size and gets overridden.
        self.call_after_refresh(self.scroll_home, animate=False)


def _render(state: TuiState) -> str:
    selection = state.selection
    result = state.last_result

    if isinstance(result, ConfigSymbolResult):
        body = provenance_lines(result.provenance)
        extra = (
            f"\u2699 symbol: {result.symbol}\n"
            f"  prompt: {result.prompt or '(none)'}\n"
            f"  choices: {', '.join(result.choices) or '(none)'}\n"
            f"  children: {', '.join(result.children) or '(none)'}"
        )
        return f"{extra}\n\n{body}"

    if isinstance(result, DoctorReport):
        check = next((c for c in result.checks if c.name == selection.id), None)
        if check is None:
            return "\u25cb Select a check to see its full detail."
        status = "\u2713 PASS" if check.ok else "\u2717 FAIL"
        return f"\u2699 check: {check.name}\n  status: {status}\n  detail: {escape(check.detail)}"

    if selection.kind == "none" or selection.id is None:
        return "\u25cb Nothing selected.\n  Press Enter on an item in Explorer to inspect it."

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
        lines = [f"\u25c6 {escape(node.label)}", f"  kind: {node.node_kind}"]
        if node.provenance is not None:
            lines.append(provenance_lines(node.provenance))
        touching = [e for e in result.edges if selection.id in (e.subject_id, e.object_id)]
        if touching:
            lines.append("")
            lines.append("  relations:")
            for edge in touching:
                lines.append(
                    f"    {edge.subject_id[:8]} \u2500\u2500{edge.predicate}\u2500\u2500> "
                    f"{edge.object_id[:8]}  "
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
            f"\u25c8 well: {well.name}\n"
            f"  purpose: {escape(well.purpose)}\n"
            f"  members: {well.member_count}\n"
            f"  created: {created_at}"
        )

    if isinstance(result, WellDetail):
        member = next((m for m in result.members if m.target_id == selection.id), None)
        if member is None:
            return "Selected item is not in the current result set."
        return (
            f"\u25c8 well: {result.well.name}\n"
            f"  target_kind: {member.target_kind}\n"
            f"  target_id: {member.target_id}\n"
            f"  note: {escape(member.note or '(none)')}\n"
            f"  added: {member.added_at.isoformat(timespec='seconds')}"
        )

    if (notes := as_list_of(result, NoteResult)) is not None:
        note = next((n for n in notes if n.id == selection.id), None)
        if note is None:
            return "Selected item is not in the current result set."
        return (
            f"\u270e note\n"
            f"  id: {note.id}\n"
            f"  target: {note.target_id} ({note.target_kind})\n"
            f"  created: {note.created_at.isoformat(timespec='seconds')}\n\n"
            f"  {escape(note.body)}"
        )

    return "Nothing to show for the current selection."


def _envelope_and_excerpt(state: TuiState) -> tuple[ProvenanceEnvelope | None, str | None]:
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
    envelope, _ = _envelope_and_excerpt(state)
    return provenance_lines(envelope) if envelope is not None else None


def excerpt_text(state: TuiState) -> str | None:
    _, excerpt = _envelope_and_excerpt(state)
    return excerpt
