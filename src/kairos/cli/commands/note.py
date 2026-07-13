"""``kairos note add|list`` sub-app."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table

from kairos.cli.errors import cli_command, console
from kairos.services.context import RuntimeContext
from kairos.services.notes import add_note, list_notes

app = typer.Typer(help="Owner-authored notes on artifacts or spans.")


@app.command("add")
@cli_command
def add(
    target_id: Annotated[str, typer.Argument(help="Artifact or span id to annotate.")],
    text: Annotated[str, typer.Argument(help="Note body.")],
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    note = add_note(ctx, target_id, text)
    console.print(f"[green]Added note[/green] {note.id} on {note.target_kind} {note.target_id}")


@app.command("list")
@cli_command
def list_(
    target_id: Annotated[str, typer.Argument(help="Artifact or span id.")],
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    notes = list_notes(ctx, target_id)
    if not notes:
        console.print("[yellow]No notes.[/yellow]")
        return

    table = Table(title=f"Notes on {target_id}")
    table.add_column("id")
    table.add_column("created_at")
    table.add_column("body")
    for note in notes:
        table.add_row(note.id, note.created_at.isoformat(timespec="seconds"), escape(note.body))
    console.print(table)
