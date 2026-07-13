"""``kairos init <workspace>``"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from kairos.cli.errors import cli_command, console
from kairos.services.workspace_init import init as init_service


@cli_command
def run(
    workspace: Annotated[
        Path, typer.Argument(help="Directory to create/initialize as a KAIROS workspace.")
    ],
    name: Annotated[str | None, typer.Option(help="Human-readable workspace name.")] = None,
) -> None:
    ctx = init_service(workspace, name=name)
    console.print(f"[green]Initialized[/green] KAIROS workspace at {ctx.workspace.root}")
    console.print(f"  database: {ctx.workspace.db_path}")
    console.print(f"  events:   {ctx.workspace.events_path}")
