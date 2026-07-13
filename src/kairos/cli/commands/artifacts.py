"""``kairos artifacts [--kind <kind>] [--limit N]``"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table

from kairos.cli.errors import cli_command, console
from kairos.services.artifacts import list_artifacts
from kairos.services.context import RuntimeContext


@cli_command
def run(
    kind: Annotated[str | None, typer.Option("--kind", help="Filter by artifact kind.")] = None,
    limit: Annotated[int, typer.Option("--limit", help="Maximum rows to show.")] = 50,
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    summaries = list_artifacts(ctx, kind=kind, limit=limit)

    table = Table(title="Artifacts")
    table.add_column("id")
    table.add_column("path")
    table.add_column("kind")
    table.add_column("status")
    table.add_column("ingested_at")

    for summary in summaries:
        table.add_row(
            summary.id,
            escape(summary.source_path),
            summary.kind,
            summary.parse_status,
            summary.ingested_at.isoformat(timespec="seconds"),
        )

    console.print(table)
