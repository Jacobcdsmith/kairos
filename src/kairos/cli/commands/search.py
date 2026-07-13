"""``kairos search <query> [--kind <kind>] [--well <name>] [--limit N]``"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table

from kairos.cli.citation import add_provenance_columns, provenance_cells
from kairos.cli.errors import cli_command, console
from kairos.services.context import RuntimeContext
from kairos.services.search import search as search_service


@cli_command
def run(
    query: Annotated[str, typer.Argument(help="FTS5 query, e.g. a word or phrase.")],
    kind: Annotated[str | None, typer.Option("--kind", help="Filter by span kind.")] = None,
    well: Annotated[str | None, typer.Option("--well", help="Scope to a coherence well.")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum hits to show.")] = 20,
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    result = search_service(ctx, query, kind=kind, well=well, limit=limit)

    if not result.hits:
        console.print("[yellow]No matches.[/yellow]")
        return

    table = Table(title=escape(f'Search: "{query}"'))
    table.add_column("path")
    add_provenance_columns(table)
    table.add_column("snippet")

    for hit in result.hits:
        table.add_row(
            escape(hit.provenance.source_path),
            *provenance_cells(hit.provenance),
            escape(hit.snippet),
        )

    console.print(table)
