from __future__ import annotations

from dataclasses import dataclass

from rich.markup import escape
from textual.widgets import ListItem, ListView, Static

from kairos.schemas.activity import ActivityEvent
from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary, SpanResult
from kairos.schemas.config import ConfigSymbolResult
from kairos.schemas.dashboard import DashboardResult
from kairos.schemas.doctor import DoctorCheck, DoctorReport
from kairos.schemas.logs import LogHit
from kairos.schemas.note import NoteResult
from kairos.schemas.search import SearchHit, SearchResult
from kairos.schemas.trace import TraceNode, TraceResult
from kairos.schemas.well import WellDetail, WellMemberResult, WellSummary
from kairos.tui.state import SelectionKind, TuiState, as_list_of

_KIND_GLYPH = {
    "markdown": "\u25a6",
    "text": "\u25a1",
    "pdf": "\u229a",
    "json": "\u2731",
    "kconfig": "\u2699",
    "log": "\u2261",
    "repository": "\u2442",
    "python": "\u03bb",
}

_LAYER_GLYPH = {
    "raw": "\u25cb",
    "extracted": "\u25cf",
    "derived": "\u25c7",
    "user": "\u270e",
}

_LAYER_TAG = {"raw": "RAW", "extracted": "EXTRACTED", "derived": "DERIVED", "user": "USER"}

_TITLE_BY_MODE = {
    "home": "Home",
    "artifacts": "Artifacts",
    "search": "Search",
    "show": "Detail",
    "trace": "Trace",
    "well": "Wells",
    "config": "Config",
    "logs": "Logs",
    "doctor": "Doctor",
    "history": "History",
    "help": "Help",
    "notes": "Notes",
}

# Every Nth row gets a printed line number in its gutter, so a long list
# gives you a sense of position (and a number to hand to Ctrl+G) without
# numbering — and cluttering — every single line.
_GUTTER_EVERY = 5


@dataclass(frozen=True, slots=True)
class _Row:
    label: str
    sublabel: str
    kind: SelectionKind | None
    target_id: str | None


def highlighted(text: str, term: str | None) -> str:
    """Escape ``text`` for Rich markup, wrapping case-insensitive matches of
    ``term`` in a reverse-video span. Escaping happens per-chunk so the
    highlight markup itself is never escaped away.
    """
    if not term:
        return escape(text)
    lower_text, lower_term = text.lower(), term.lower()
    if lower_term not in lower_text:
        return escape(text)
    chunks: list[str] = []
    i = 0
    while i < len(text):
        idx = lower_text.find(lower_term, i)
        if idx == -1:
            chunks.append(escape(text[i:]))
            break
        chunks.append(escape(text[i:idx]))
        chunks.append(f"[reverse]{escape(text[idx : idx + len(term)])}[/reverse]")
        i = idx + len(term)
    return "".join(chunks)


class ExplorerItem(ListItem):
    def __init__(self, row: _Row, index: int, query_term: str | None = None) -> None:
        gutter = f"{index + 1:>4} " if (index + 1) % _GUTTER_EVERY == 0 else "     "
        text = f"{gutter}{highlighted(row.label, query_term)}"
        if row.sublabel:
            text += f"\n     [dim]{escape(row.sublabel)}[/dim]"
        super().__init__(Static(text))
        self.kind: SelectionKind | None = row.kind
        self.target_id: str | None = row.target_id


class ExplorerPane(ListView):
    def refresh_from_state(self, state: TuiState) -> None:
        self.clear()
        rows = _rows_for(state)
        query_term = _query_term(state)
        for index, row in enumerate(rows):
            self.append(ExplorerItem(row, index, query_term))
        if rows:
            self.index = 0
        self.border_title = f"{_TITLE_BY_MODE.get(state.mode, state.mode.title())} ({len(rows)})"
        self.call_after_refresh(self._update_scroll_indicators)

    def selected_reference(self) -> tuple[SelectionKind, str] | None:
        item = self.highlighted_child
        if isinstance(item, ExplorerItem) and item.kind is not None and item.target_id is not None:
            return item.kind, item.target_id
        return None

    def on_list_viewhighlighted(self, event: ListView.Highlighted) -> None:
        self.call_after_refresh(self._update_scroll_indicators)

    def _update_scroll_indicators(self) -> None:
        max_scroll = self.max_scroll_y
        if max_scroll <= 0:
            self.border_subtitle = ""
            return
        can_scroll_up = self.scroll_y > 0.5
        can_scroll_down = self.scroll_y < max_scroll - 0.5
        if can_scroll_up and can_scroll_down:
            self.border_subtitle = "▲▼ more"
        elif can_scroll_up:
            self.border_subtitle = "▲ top"
        elif can_scroll_down:
            self.border_subtitle = "▼ more below"
        else:
            self.border_subtitle = ""


def _query_term(state: TuiState) -> str | None:
    result = state.last_result
    if isinstance(result, SearchResult):
        return result.query
    if isinstance(result, TraceResult):
        return result.query
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
    if isinstance(result, DashboardResult):
        return _dashboard_rows(result)
    if result is None and state.mode == "home":
        return [_Row("○  No local activity yet.", "", None, None)]
    return []


def _activity_row(event: ActivityEvent) -> _Row:
    return _Row(
        f"\u25b8  {event.event_type}",
        event.occurred_at.isoformat(timespec="seconds"),
        None,
        None,
    )


def _artifact_row(a: ArtifactSummary) -> _Row:
    glyph = _KIND_GLYPH.get(a.kind, "\u25aa")
    ingested = a.ingested_at.isoformat(timespec="seconds")
    return _Row(
        f"{glyph}  [{a.kind}] {a.source_path}",
        f"{a.parse_status} \u00b7 {a.size_bytes}B \u00b7 {ingested}",
        "artifact",
        a.id,
    )


def _search_hit_row(h: SearchHit) -> _Row:
    tag = _LAYER_TAG[h.provenance.layer]
    glyph = _LAYER_GLYPH.get(h.provenance.layer, "\u25cf")
    return _Row(
        f"{glyph}  {h.provenance.source_path}",
        f"{h.provenance.locator_str} \u00b7 {tag}",
        "span",
        h.span_id,
    )


def _span_row(s: SpanResult) -> _Row:
    tag = _LAYER_TAG[s.provenance.layer]
    glyph = _LAYER_GLYPH.get(s.provenance.layer, "\u25cf")
    first_line = s.text_content.strip().splitlines()[0] if s.text_content.strip() else s.span_kind
    label = f"  {glyph} [{s.span_kind}] {first_line[:56]}"
    return _Row(label, f"{s.provenance.locator_str} \u00b7 {tag}", "span", s.span_id)


def _trace_node_row(n: TraceNode) -> _Row:
    tag = _LAYER_TAG[n.provenance.layer] if n.provenance else "DERIVED"
    kind: SelectionKind = n.node_kind if n.node_kind in ("entity", "span", "artifact") else "none"
    glyph = "\u25c6" if n.node_kind == "entity" else "\u25cb" if n.node_kind == "span" else "\u25a1"
    return _Row(f"{glyph}  [{n.node_kind}] {n.label[:56]}", tag, kind, n.node_id)


def _config_rows(result: ConfigSymbolResult) -> list[_Row]:
    rows = [
        _Row(f"\u2699  symbol {result.symbol}", f"type={result.symbol_type or '?'}", None, None),
        _Row(f"  \u2514 default: {result.default or '(none)'}", "", None, None),
        _Row(f"  \u2514 depends_on: {result.depends_on or '(none)'}", "", None, None),
    ]
    rows.extend(_Row(f"  \u251c child: {c}", "", None, None) for c in result.children)
    return rows


def _log_row(h: LogHit) -> _Row:
    tag = _LAYER_TAG[h.provenance.layer]
    glyph = _LAYER_GLYPH.get(h.provenance.layer, "\u25cf")
    level_glyph = "\u2717" if h.level == "ERROR" else "\u26a0" if h.level == "WARNING" else "\u25b8"
    label = f"{glyph}  {level_glyph} line {h.line_number}: {h.message[:46]}"
    sub = f"{h.level or ''} {h.component or ''} \u00b7 {tag}".strip()
    return _Row(label, sub, "span", h.provenance.locator_str)


def _doctor_row(c: DoctorCheck) -> _Row:
    glyph = "\u2713" if c.ok else "\u2717"
    color = "green" if c.ok else "red"
    return _Row(
        f"[{color}]{glyph}[/{color}]  {c.name}",
        c.detail[:56],
        "doctor_check",
        c.name,
    )


def _well_summary_row(w: WellSummary) -> _Row:
    sub = f"{w.purpose} \u00b7 {w.member_count} member(s)"
    return _Row(f"\u25c8  {w.name}", sub, "well", w.name)


def _well_member_row(m: WellMemberResult) -> _Row:
    kind: SelectionKind = "artifact" if m.target_kind == "artifact" else "span"
    return _Row(f"\u251c  {m.target_id}", m.note or "", kind, m.target_id)


def _note_row(n: NoteResult) -> _Row:
    sub = f"on {n.target_id} · {n.created_at.isoformat(timespec='seconds')}"
    return _Row(f"✎  {n.body[:56]}", sub, "note", n.id)


def _dashboard_rows(d: DashboardResult) -> list[_Row]:
    rows: list[_Row] = []
    rows.append(_Row("▣  Artifacts", str(d.total_artifacts), "artifact", "dashboard:artifacts"))
    rows.append(_Row("◈  Entities", str(d.total_entities), "entity", "dashboard:entities"))
    rows.append(_Row("◉  Relations", str(d.total_relations), "relation", "dashboard:relations"))
    rows.append(_Row("▤  Spans", str(d.total_spans), "span", "dashboard:spans"))
    rows.append(_Row("◈  Wells", str(d.total_wells), "well", "dashboard:wells"))
    if d.parse_errors:
        rows.append(_Row("⚠  Parse errors", str(d.parse_errors), "artifact", "dashboard:errors"))
    # Breakdown by kind
    for bk in d.artifacts_by_kind:
        sub = f"{bk.count} total · {bk.status_ok} ok, {bk.status_error} errors"
        rows.append(_Row(f"  ▸  {bk.kind}", sub, "artifact", f"dashboard:kind:{bk.kind}"))
    # Recent activity
    for ev in d.recent_activity:
        rows.append(
            _Row(
                f"  ▸  {ev.event_type}",
                ev.occurred_at.isoformat(timespec="minutes"),
                None,
                None,
            )
        )
    return rows or [_Row("○  Empty workspace — try :ingest .", "", None, None)]
