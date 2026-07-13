"""``kairos ingest <path> [--recursive]``"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table

from kairos.cli.errors import cli_command, console
from kairos.services.context import RuntimeContext
from kairos.services.ingest import ingest as ingest_service


@cli_command
def run(
    path: Annotated[Path, typer.Argument(help="File or directory to ingest.")],
    recursive: Annotated[
        bool, typer.Option("--recursive", help="Ingest a directory tree.")
    ] = False,
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    report = ingest_service(ctx, path, recursive=recursive)

    if not report.outcomes:
        console.print("[yellow]No artifacts ingested.[/yellow]")
        return

    table = Table(title="Ingested")
    table.add_column("id")
    table.add_column("path")
    table.add_column("kind")
    table.add_column("status")
    table.add_column("spans", justify="right")
    table.add_column("note")

    for outcome in report.outcomes:
        note = "already ingested (same content hash)" if outcome.already_ingested else ""
        if outcome.diagnostics:
            note = f"{len(outcome.diagnostics)} diagnostic(s)"
        table.add_row(
            outcome.artifact.id,
            escape(outcome.artifact.source_path),
            outcome.artifact.kind,
            outcome.artifact.parse_status,
            str(outcome.span_count),
            escape(note),
        )

    console.print(table)
    for outcome in report.outcomes:
        for diag in outcome.diagnostics:
            console.print(
                f"  [yellow]diagnostic[/yellow] {escape(diag.source_path)}: {escape(diag.message)}"
            )
