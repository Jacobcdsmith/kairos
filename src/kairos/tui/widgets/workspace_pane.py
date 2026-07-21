from __future__ import annotations

from rich.markup import escape
from rich.table import Table
from rich.text import Text
from textual.widgets import RichLog

from kairos.cli.citation import add_provenance_columns, provenance_cells
from kairos.schemas.activity import ActivityEvent
from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary
from kairos.schemas.config import ConfigSymbolResult
from kairos.schemas.dashboard import DashboardResult
from kairos.schemas.doctor import DoctorReport
from kairos.schemas.logs import LogHit
from kairos.schemas.note import NoteResult
from kairos.schemas.search import SearchResult
from kairos.schemas.trace import TraceResult
from kairos.schemas.well import WellDetail, WellSummary
from kairos.tui.state import ActivityEntry, TuiState, as_list_of

_CMD_GLYPH = "\u2b22"
_OK_GLYPH = "\u2713"
_ERR_GLYPH = "\u2717"
_ARROW = "\u25b8"


class WorkspacePane(RichLog):
    def __init__(self) -> None:
        super().__init__(wrap=True, markup=True, highlight=False, id="workspace-pane")

    def append_entry(self, entry: ActivityEntry, state: TuiState) -> None:
        self.write(Text(f"{_CMD_GLYPH} {entry.command}", style="bold cyan"))
        if entry.status == "error":
            self.write(Text(f"  {_ERR_GLYPH} {entry.summary}", style="red"))
        else:
            result = _render_result(state)
            if isinstance(result, Text):
                self.write(Text(f"  {_OK_GLYPH} ", style="green") + result)
            else:
                self.write(Text(f"  {_OK_GLYPH}", style="green"))
                self.write(result)
        self.write("")


def _render_result(state: TuiState) -> object:
    result = state.last_result

    if isinstance(result, DashboardResult):
        return _render_dashboard(result)

    if (events := as_list_of(result, ActivityEvent)) is not None:
        table = Table(title="\u25cb Recent local activity", show_lines=False, padding=(0, 2))
        table.add_column("occurred_at", style="dim")
        table.add_column("event_type", style="cyan")
        for event in events:
            table.add_row(event.occurred_at.isoformat(timespec="seconds"), event.event_type)
        return table

    if (artifacts := as_list_of(result, ArtifactSummary)) is not None:
        table = Table(title="\u25a1 Artifacts", show_lines=False, padding=(0, 2))
        table.add_column("id", style="dim", max_width=10)
        table.add_column("path", style="cyan")
        table.add_column("kind", style="magenta")
        table.add_column("status", style="green")
        for a in artifacts:
            table.add_row(a.id[:8], escape(a.source_path), a.kind, a.parse_status)
        return table

    if isinstance(result, SearchResult):
        table = Table(
            title=f'\u25cf Search: "{escape(result.query)}"', show_lines=False, padding=(0, 2)
        )
        table.add_column("path", style="cyan")
        add_provenance_columns(table)
        table.add_column("snippet", style="dim")
        for hit in result.hits:
            table.add_row(
                escape(hit.provenance.source_path),
                *provenance_cells(hit.provenance),
                escape(hit.snippet),
            )
        return table

    if isinstance(result, ArtifactDetail):
        table = Table(
            title=f"\u25a1 {escape(result.artifact.source_path)}", show_lines=False, padding=(0, 2)
        )
        table.add_column("span_kind", style="magenta")
        add_provenance_columns(table, include_locator=True)
        for span in result.spans:
            table.add_row(span.span_kind, *provenance_cells(span.provenance))
        return table

    if isinstance(result, TraceResult):
        text = Text()
        text.append(f"\u25c6 trace: {result.query}\n", style="bold cyan")
        for edge in result.edges:
            text.append(
                f"  {edge.subject_id[:8]} ", style="dim"
            )
            text.append(f"\u2500\u2500{edge.predicate}\u2500\u2500> ", style="yellow")
            text.append(f"{edge.object_id[:8]}\n", style="dim")
            text.append(
                f"    ({edge.layer}, rule={edge.derivation_rule or 'n/a'})\n", style="dim"
            )
        if not result.edges:
            text.append("  (no explicit relations found)\n", style="dim italic")
        return text

    if isinstance(result, ConfigSymbolResult):
        text = Text()
        text.append(f"\u2699 symbol: {result.symbol}\n", style="bold cyan")
        text.append(f"  prompt: {result.prompt or '(none)'}\n")
        text.append(f"  type: {result.symbol_type or '(none)'}\n")
        text.append(f"  default: {result.default or '(none)'}\n")
        text.append(f"  depends_on: {result.depends_on or '(none)'}\n")
        text.append(f"  choices: {', '.join(result.choices) or '(none)'}\n")
        text.append(f"  children: {', '.join(result.children) or '(none)'}")
        return text

    if (log_hits := as_list_of(result, LogHit)) is not None:
        table = Table(title="\u2261 Log lines", show_lines=False, padding=(0, 2))
        table.add_column("line", style="dim", justify="right")
        table.add_column("level", style="bold")
        table.add_column("message")
        for hit in log_hits:
            if hit.level == "ERROR":
                level_style = "red"
            elif hit.level == "WARNING":
                level_style = "yellow"
            else:
                level_style = ""
            level_text = f"[{hit.level or ''}]" if level_style else (hit.level or "")
            table.add_row(str(hit.line_number), level_text, escape(hit.message))
        return table

    if isinstance(result, DoctorReport):
        table = Table(title="\u2699 kairos doctor", show_lines=False, padding=(0, 2))
        table.add_column("check", style="cyan")
        table.add_column("status", justify="center")
        table.add_column("detail", style="dim")
        for check in result.checks:
            status_text = "PASS" if check.ok else "FAIL"
            table.add_row(check.name, status_text, escape(check.detail))
        return table

    if (wells := as_list_of(result, WellSummary)) is not None:
        table = Table(title="\u25c8 Coherence wells", show_lines=False, padding=(0, 2))
        table.add_column("name", style="cyan")
        table.add_column("purpose", style="dim")
        table.add_column("members", justify="right", style="green")
        for well in wells:
            table.add_row(well.name, escape(well.purpose), str(well.member_count))
        return table

    if isinstance(result, WellDetail):
        table = Table(
            title=f"\u25c8 {escape(result.well.name)} \u2014 {escape(result.well.purpose)}",
            show_lines=False,
            padding=(0, 2),
        )
        table.add_column("target_kind", style="magenta")
        table.add_column("target_id", style="cyan")
        table.add_column("note", style="dim")
        for member in result.members:
            table.add_row(member.target_kind, member.target_id, escape(member.note or ""))
        return table

    if (notes := as_list_of(result, NoteResult)) is not None:
        table = Table(title="\u270e Notes", show_lines=False, padding=(0, 2))
        table.add_column("id", style="dim", max_width=10)
        table.add_column("created_at", style="dim")
        table.add_column("body")
        for note in notes:
            created_at = note.created_at.isoformat(timespec="seconds")
            table.add_row(note.id[:8], created_at, escape(note.body))
        return table

    return Text("(○ no results)", style="dim italic")


def _render_dashboard(d: DashboardResult) -> object:
    from rich.console import Group
    from rich.table import Table

    items: list[object] = []

    # Metrics row
    metrics = Table(show_header=False, show_lines=False, padding=(0, 3), box=None)
    metrics.add_column("label", style="bold cyan")
    metrics.add_column("value", style="bold white", justify="right")
    for label, value, color in [
        ("Artifacts", str(d.total_artifacts), "bold white"),
        ("Entities", str(d.total_entities), "bold white"),
        ("Relations", str(d.total_relations), "bold white"),
        ("Spans", str(d.total_spans), "bold white"),
        ("Wells", str(d.total_wells), "bold white"),
    ]:
        metrics.add_row(label, f"[{color}]{value}[/{color}]")

    items.append(metrics)
    items.append("")

    # Breakdown by kind
    if d.artifacts_by_kind:
        breakdown = Table(
            title="Artifact breakdown", show_lines=False, padding=(0, 2), box=None
        )
        breakdown.add_column("kind", style="cyan")
        breakdown.add_column("count", justify="right")
        breakdown.add_column("ok", justify="right")
        breakdown.add_column("errors", justify="right")
        for bk in d.artifacts_by_kind:
            err_style = "red" if bk.status_error else "green"
            breakdown.add_row(
                bk.kind,
                str(bk.count),
                "[green]" + str(bk.status_ok) + "[/green]",
                f"[{err_style}]{bk.status_error}[/{err_style}]",
            )
        items.append(breakdown)

    if d.parse_errors:
        items.append(f"[red]⚠  {d.parse_errors} parse error(s) across all artifacts[/red]")

    # Recent activity
    if d.recent_activity:
        events = Table(
            title="Recent activity", show_lines=False, padding=(0, 2), box=None
        )
        events.add_column("time", style="dim")
        events.add_column("event", style="cyan")
        for ev in d.recent_activity:
            events.add_row(ev.occurred_at.isoformat(timespec="minutes"), ev.event_type)
        items.append("")
        items.append(events)

    return Group(*items)
