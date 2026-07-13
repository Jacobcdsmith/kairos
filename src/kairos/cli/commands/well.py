"""``kairos well create|add|remove|show|list`` sub-app."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table

from kairos.cli.errors import cli_command, console
from kairos.services.context import RuntimeContext
from kairos.services.wells import (
    add_member,
    create_well,
    list_all_wells,
    remove_member,
    show_well,
)

app = typer.Typer(help="Coherence wells: owner-curated working sets.")


@app.command("create")
@cli_command
def create(
    name: Annotated[str, typer.Argument(help="Well name, must be unique.")],
    purpose: Annotated[str, typer.Option("--purpose", help="Why this well exists.")],
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    well = create_well(ctx, name, purpose)
    console.print(f"[green]Created well[/green] {escape(well.name)} ({well.id})")


@app.command("add")
@cli_command
def add(
    well_name: Annotated[str, typer.Argument(help="Well name.")],
    member_id: Annotated[str, typer.Argument(help="Artifact or span id to add.")],
    note: Annotated[
        str | None, typer.Option("--note", help="Optional note on this membership.")
    ] = None,
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    member = add_member(ctx, well_name, member_id, note=note)
    console.print(
        f"[green]Added[/green] {member.target_kind} {member.target_id} to {escape(well_name)}"
    )


@app.command("remove")
@cli_command
def remove(
    well_name: Annotated[str, typer.Argument(help="Well name.")],
    member_id: Annotated[str, typer.Argument(help="Membership id, from `well show`.")],
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    remove_member(ctx, well_name, member_id)
    console.print(f"[green]Removed[/green] {member_id} from {escape(well_name)}")


@app.command("show")
@cli_command
def show(well_name: Annotated[str, typer.Argument(help="Well name.")]) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    detail = show_well(ctx, well_name)

    console.print(
        f"[bold]{escape(detail.well.name)}[/bold] — {escape(detail.well.purpose)} "
        f"({detail.well.member_count} members)"
    )
    if not detail.members:
        return

    table = Table()
    table.add_column("member_id")
    table.add_column("target_kind")
    table.add_column("target_id")
    table.add_column("note")
    for member in detail.members:
        table.add_row(member.id, member.target_kind, member.target_id, escape(member.note or ""))
    console.print(table)


@app.command("list")
@cli_command
def list_() -> None:
    ctx = RuntimeContext.open(Path.cwd())
    wells = list_all_wells(ctx)
    if not wells:
        console.print("[yellow]No coherence wells.[/yellow]")
        return

    table = Table(title="Coherence wells")
    table.add_column("name")
    table.add_column("purpose")
    table.add_column("members", justify="right")
    for well in wells:
        table.add_row(escape(well.name), escape(well.purpose), str(well.member_count))
    console.print(table)
