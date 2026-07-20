"""``kairos init <workspace> [--interactive]``"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.prompt import Confirm, Prompt

from kairos.cli.errors import cli_command, console
from kairos.services.ingest import ingest as ingest_service
from kairos.services.wells import create_well
from kairos.services.workspace_init import init as init_service


@cli_command
def run(
    workspace: Annotated[
        Path, typer.Argument(help="Directory to create/initialize as a KAIROS workspace.")
    ],
    name: Annotated[str | None, typer.Option(help="Human-readable workspace name.")] = None,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            "-i",
            help="Interactive setup wizard with guided prompts.",
        ),
    ] = False,
) -> None:
    if interactive:
        _run_wizard(workspace, name)
    else:
        _run_simple(workspace, name)


def _run_simple(workspace: Path, name: str | None) -> None:
    ctx = init_service(workspace, name=name)
    console.print(f"[green]Initialized[/green] KAIROS workspace at {ctx.workspace.root}")
    console.print(f"  database: {ctx.workspace.db_path}")
    console.print(f"  events:   {ctx.workspace.events_path}")
    console.print()
    console.print("[dim]Next steps:[/dim]")
    console.print("  kairos ingest <path> [--recursive]")
    console.print("  kairos search <query>")
    console.print("  kairos tui")


def _run_wizard(workspace: Path, name: str | None) -> None:
    console.print()
    console.print("[bold cyan]Welcome to KAIROS[/bold cyan]")
    console.print("[dim]A local-first, source-grounded workspace for your technical corpus.[/dim]")
    console.print()

    console.print("[bold]Step 1: Workspace location[/bold]")
    workspace_str = Prompt.ask(
        "  Workspace directory",
        default=str(workspace),
    )
    workspace = Path(workspace_str).expanduser().resolve()

    if workspace.exists():
        console.print(f"  [dim]Using existing directory: {workspace}[/dim]")
    else:
        console.print(f"  [dim]Will create: {workspace}[/dim]")

    console.print()
    console.print("[bold]Step 2: Workspace name[/bold]")
    default_name = name or workspace.name
    workspace_name = Prompt.ask("  Human-readable name", default=default_name)

    console.print()
    console.print("[bold]Step 3: Initial content[/bold]")
    console.print("  [dim]What would you like to ingest first?[/dim]")
    console.print("  [dim](Leave blank to skip — you can always ingest later)[/dim]")

    ingest_paths: list[Path] = []
    while True:
        path_str = Prompt.ask("  Path to ingest (file or directory)", default="")
        if not path_str:
            break
        path = Path(path_str).expanduser().resolve()
        if not path.exists():
            console.print(f"  [yellow]Warning: {path} does not exist, skipping[/yellow]")
        else:
            ingest_paths.append(path)
            console.print(f"  [green]Added:[/green] {path}")

    console.print()
    console.print("[bold]Step 4: Coherence well (optional)[/bold]")
    console.print("  [dim]A coherence well is a curated working set of related artifacts.[/dim]")
    create_initial_well = Confirm.ask("  Create an initial well?", default=False)

    well_name: str | None = None
    well_purpose: str | None = None
    if create_initial_well:
        well_name = Prompt.ask("  Well name", default="focus")
        well_purpose = Prompt.ask("  Purpose", default="My current focus area")

    console.print()
    console.print("[bold]Creating workspace...[/bold]")
    ctx = init_service(workspace, name=workspace_name)
    console.print(f"  [green]Created[/green] {ctx.workspace.root}")

    if ingest_paths:
        console.print()
        console.print("[bold]Ingesting content...[/bold]")
        for path in ingest_paths:
            recursive = path.is_dir()
            report = ingest_service(ctx, path, recursive=recursive)
            new_count = sum(1 for o in report.outcomes if not o.already_ingested)
            console.print(f"  [green]Ingested[/green] {path} ({new_count} new artifact(s))")

    if well_name and well_purpose:
        console.print()
        console.print("[bold]Creating coherence well...[/bold]")
        create_well(ctx, well_name, well_purpose)
        console.print(f"  [green]Created well:[/green] {well_name}")

    console.print()
    console.print("[bold green]Setup complete![/bold green]")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print("  [cyan]kairos tui[/cyan]                     Launch the interactive TUI")
    console.print("  [cyan]kairos search <query>[/cyan]          Search your corpus")
    console.print("  [cyan]kairos artifacts[/cyan]               List all ingested artifacts")
    console.print("  [cyan]kairos trace <term>[/cyan]            Trace relations across sources")
    console.print()
    console.print("[dim]Run 'kairos --help' for the full command reference.[/dim]")
