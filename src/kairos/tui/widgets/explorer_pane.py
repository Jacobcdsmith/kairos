"""The Explorer pane: "what can I navigate from here?" Renders a list keyed
off the current mode's ``last_result``, one row per navigable item, each
visibly tagged with its provenance layer (never color-only — see
docs/tli.md's provenance legend).
"""

from __future__ import annotations

from dataclasses import dataclass

from rich.markup import escape
from textual.widgets import ListItem, ListView, Static

from kairos.schemas.activity import ActivityEvent
from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary, SpanResult
from kairos.schemas.config import ConfigSymbolResult
from kairos.schemas.doctor import DoctorCheck, DoctorReport
from kairos.schemas.logs import LogHit
from kairos.schemas.note import NoteResult
from kairos.schemas.search import SearchHit, SearchResult
from kairos.schemas.trace import TraceNode, TraceResult
from kairos.schemas.well import WellDetail, WellMemberResult, WellSummary
from kairos.tui.state import SelectionKind, TuiState, as_list_of

_LAYER_TAG = {"raw": "RAW", "extracted": "EXTRACTED", "derived": "DERIVED", "user": "USER"}


@dataclass(frozen=True, slots=True)
class _Row:
    label: str
    sublabel: str
    kind: SelectionKind | None
    target_id: str | None


class ExplorerItem(ListItem):
    def __init__(self, row: _Row) -> None:
        text = escape(row.label)
        if row.sublabel:
            text += f"\n[dim]{escape(row.sublabel)}[/dim]"
        super().__init__(Static(text))
        self.kind: SelectionKind | None = row.kind
        self.target_id: str | None = row.target_id


class ExplorerPane(ListView):
    def refresh_from_state(self, state: TuiState) -> None:
        self.clear()
        rows = _rows_for(state)
        for row in rows:
            self.append(ExplorerItem(row))
        if rows:
            # ListView.clear() resets `index` to None; without this, the
            # first item is never highlighted and Enter has nothing to
            # select until the user presses Up/Down at least once.
            self.index = 0

    def selected_reference(self) -> tuple[SelectionKind, str] | None:
        item = self.highlighted_child
        if isinstance(item, ExplorerItem) and item.kind is not None and item.target_id is not None:
            return item.kind, item.target_id
        return None


def _rows_for(state: TuiState) -> list[_Row]:
    result = state.last_result
    if (events := as_list_of(result, ActivityEvent)) is not None:
        return [_activity_row(e) for e in events]
    if (artifacts := as_list_of(result, ArtifactSummary)) is not None:
        return [_artifact_row(a) for a in artifacts]
    if isinstance(result, SearchResult):
        return [_search_hit_row(h) for h in result.hits]
    if isinstance(result, ArtifactDetail):
        return [_artifact_row(result.artifact), *[_span_row(s) for s in result.spans]]
    if isinstance(result, TraceResult):
        return [_trace_node_row(n) for n in result.nodes]
    if isinstance(result, ConfigSymbolResult):
        return _config_rows(result)
    if (log_hits := as_list_of(result, LogHit)) is not None:
        return [_log_row(h) for h in log_hits]
    if isinstance(result, DoctorReport):
        return [_doctor_row(c) for c in result.checks]
    if (wells := as_list_of(result, WellSummary)) is not None:
        return [_well_summary_row(w) for w in wells]
    if isinstance(result, WellDetail):
        return [_well_member_row(m) for m in result.members]
    if (notes := as_list_of(result, NoteResult)) is not None:
        return [_note_row(n) for n in notes]
    if result is None and state.mode == "home":
        return [_Row("No local activity yet.", "", None, None)]
    return []


def _activity_row(event: ActivityEvent) -> _Row:
    return _Row(event.event_type, event.occurred_at.isoformat(timespec="seconds"), None, None)


def _artifact_row(a: ArtifactSummary) -> _Row:
    return _Row(
        f"[{a.kind}] {a.source_path}",
        f"{a.parse_status} · {a.size_bytes}B · {a.ingested_at.isoformat(timespec='seconds')}",
        "artifact",
        a.id,
    )


def _search_hit_row(h: SearchHit) -> _Row:
    tag = _LAYER_TAG[h.provenance.layer]
    return _Row(h.provenance.source_path, f"{h.provenance.locator_str} · {tag}", "span", h.span_id)


def _span_row(s: SpanResult) -> _Row:
    tag = _LAYER_TAG[s.provenance.layer]
    first_line = s.text_content.strip().splitlines()[0] if s.text_content.strip() else s.span_kind
    label = f"[{s.span_kind}] {first_line[:60]}"
    return _Row(label, f"{s.provenance.locator_str} · {tag}", "span", s.span_id)


def _trace_node_row(n: TraceNode) -> _Row:
    tag = _LAYER_TAG[n.provenance.layer] if n.provenance else "DERIVED"
    kind: SelectionKind = n.node_kind if n.node_kind in ("entity", "span", "artifact") else "none"
    return _Row(f"[{n.node_kind}] {n.label[:60]}", tag, kind, n.node_id)


def _config_rows(result: ConfigSymbolResult) -> list[_Row]:
    rows = [
        _Row(f"symbol {result.symbol}", f"type={result.symbol_type or '?'}", None, None),
        _Row(f"default: {result.default or '(none)'}", "", None, None),
        _Row(f"depends_on: {result.depends_on or '(none)'}", "", None, None),
    ]
    rows.extend(_Row(f"child: {c}", "", None, None) for c in result.children)
    return rows


def _log_row(h: LogHit) -> _Row:
    tag = _LAYER_TAG[h.provenance.layer]
    label = f"line {h.line_number}: {h.message[:50]}"
    sub = f"{h.level or ''} {h.component or ''} · {tag}".strip()
    return _Row(label, sub, "span", h.provenance.locator_str)


def _doctor_row(c: DoctorCheck) -> _Row:
    return _Row(
        c.name, ("PASS" if c.ok else "FAIL") + " · " + c.detail[:60], "doctor_check", c.name
    )


def _well_summary_row(w: WellSummary) -> _Row:
    return _Row(w.name, f"{w.purpose} · {w.member_count} member(s)", "well", w.name)


def _well_member_row(m: WellMemberResult) -> _Row:
    kind: SelectionKind = "artifact" if m.target_kind == "artifact" else "span"
    return _Row(m.target_id, m.note or "", kind, m.target_id)


def _note_row(n: NoteResult) -> _Row:
    sub = f"on {n.target_id} · {n.created_at.isoformat(timespec='seconds')}"
    return _Row(n.body[:60], sub, "note", n.id)
