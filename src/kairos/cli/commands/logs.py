"""``kairos logs <query> [--before N] [--after N] [--level <level>]``"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table

from kairos.cli.citation import add_provenance_columns, provenance_cells
from kairos.cli.errors import cli_command, console
from kairos.services.context import RuntimeContext
from kairos.services.logs_query import query_logs


@cli_command
def run(
    query: Annotated[str, typer.Argument(help="FTS5 query over log messages.")],
    before: Annotated[
        int, typer.Option("--before", help="Lines of context before each match.")
    ] = 0,
    after: Annotated[int, typer.Option("--after", help="Lines of context after each match.")] = 0,
    level: Annotated[
        str | None, typer.Option("--level", help="Filter matches by log level.")
    ] = None,
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    hits = query_logs(ctx, query, before=before, after=after, level=level)

    if not hits:
        console.print("[yellow]No matches.[/yellow]")
        return

    table = Table(title=escape(f'Logs: "{query}"'))
    table.add_column("path")
    table.add_column("line")
    add_provenance_columns(table)
    table.add_column("timestamp")
    table.add_column("level")
    table.add_column("component")
    table.add_column("message")

    for hit in hits:
        table.add_row(
            escape(hit.provenance.source_path),
            str(hit.line_number),
            *provenance_cells(hit.provenance),
            hit.timestamp or "",
            hit.level or "",
            escape(hit.component or ""),
            escape(hit.message),
        )

    console.print(table)
