"""The Workspace/Activity pane: the primary living pane. An append-only
transcript of every command run this session and its result — structured
tables/trees, not a raw terminal capture, but the same "what did I just do"
feel. History (past entries) stays scrollable in the same log; nothing is
re-queried to redraw it.
"""

from __future__ import annotations

from rich.markup import escape
from rich.table import Table
from rich.text import Text
from textual.widgets import RichLog

from kairos.cli.citation import add_provenance_columns, provenance_cells
from kairos.schemas.activity import ActivityEvent
from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary
from kairos.schemas.config import ConfigSymbolResult
from kairos.schemas.doctor import DoctorReport
from kairos.schemas.logs import LogHit
from kairos.schemas.note import NoteResult
from kairos.schemas.search import SearchResult
from kairos.schemas.trace import TraceResult
from kairos.schemas.well import WellDetail, WellSummary
from kairos.tui.state import ActivityEntry, TuiState, as_list_of


class WorkspacePane(RichLog):
    def __init__(self) -> None:
        super().__init__(wrap=True, markup=True, highlight=False, id="workspace-pane")

    def append_entry(self, entry: ActivityEntry, state: TuiState) -> None:
        self.write(Text(f"> {entry.command}", style="bold"))
        if entry.status == "error":
            self.write(Text(entry.summary, style="red"))
        else:
            self.write(_render_result(state))
        self.write("")


def _render_result(state: TuiState) -> object:
    result = state.last_result

    if (events := as_list_of(result, ActivityEvent)) is not None:
        table = Table(title="Recent local activity")
        table.add_column("occurred_at")
        table.add_column("event_type")
        for event in events:
            table.add_row(event.occurred_at.isoformat(timespec="seconds"), event.event_type)
        return table

    if (artifacts := as_list_of(result, ArtifactSummary)) is not None:
        table = Table(title="Artifacts")
        table.add_column("id")
        table.add_column("path")
        table.add_column("kind")
        table.add_column("status")
        for a in artifacts:
            table.add_row(a.id, escape(a.source_path), a.kind, a.parse_status)
        return table

    if isinstance(result, SearchResult):
        table = Table(title=escape(f'Search: "{result.query}"'))
        table.add_column("path")
        add_provenance_columns(table)
        table.add_column("snippet")
        for hit in result.hits:
            table.add_row(
                escape(hit.provenance.source_path),
                *provenance_cells(hit.provenance),
                escape(hit.snippet),
            )
        return table

    if isinstance(result, ArtifactDetail):
        table = Table(title=escape(result.artifact.source_path))
        table.add_column("span_kind")
        add_provenance_columns(table, include_locator=True)
        for span in result.spans:
            table.add_row(span.span_kind, *provenance_cells(span.provenance))
        return table

    if isinstance(result, TraceResult):
        text = Text()
        text.append(f"trace: {result.query}\n", style="bold")
        for edge in result.edges:
            text.append(
                f"  {edge.subject_id[:8]} --{edge.predicate}--> {edge.object_id[:8]}  "
                f"({edge.layer}, rule={edge.derivation_rule or 'n/a'})\n"
            )
        if not result.edges:
            text.append("  (no explicit relations found)\n")
        return text

    if isinstance(result, ConfigSymbolResult):
        return Text(
            f"symbol: {result.symbol}\nprompt: {result.prompt or '(none)'}\n"
            f"type: {result.symbol_type or '(none)'}\ndefault: {result.default or '(none)'}\n"
            f"depends_on: {result.depends_on or '(none)'}\n"
            f"choices: {', '.join(result.choices) or '(none)'}\n"
            f"children: {', '.join(result.children) or '(none)'}"
        )

    if (log_hits := as_list_of(result, LogHit)) is not None:
        table = Table(title="Log lines")
        table.add_column("line")
        table.add_column("level")
        table.add_column("message")
        for hit in log_hits:
            table.add_row(str(hit.line_number), hit.level or "", escape(hit.message))
        return table

    if isinstance(result, DoctorReport):
        table = Table(title="kairos doctor")
        table.add_column("check")
        table.add_column("status")
        table.add_column("detail")
        for check in result.checks:
            table.add_row(check.name, "PASS" if check.ok else "FAIL", escape(check.detail))
        return table

    if (wells := as_list_of(result, WellSummary)) is not None:
        table = Table(title="Coherence wells")
        table.add_column("name")
        table.add_column("purpose")
        table.add_column("members", justify="right")
        for well in wells:
            table.add_row(well.name, escape(well.purpose), str(well.member_count))
        return table

    if isinstance(result, WellDetail):
        table = Table(title=escape(f"{result.well.name} — {result.well.purpose}"))
        table.add_column("target_kind")
        table.add_column("target_id")
        table.add_column("note")
        for member in result.members:
            table.add_row(member.target_kind, member.target_id, escape(member.note or ""))
        return table

    if (notes := as_list_of(result, NoteResult)) is not None:
        table = Table(title="Notes")
        table.add_column("id")
        table.add_column("created_at")
        table.add_column("body")
        for note in notes:
            created_at = note.created_at.isoformat(timespec="seconds")
            table.add_row(note.id, created_at, escape(note.body))
        return table

    return Text("(no results)", style="dim")
