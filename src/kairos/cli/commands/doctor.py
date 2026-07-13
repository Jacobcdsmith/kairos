"""``kairos doctor``"""

from __future__ import annotations

from pathlib import Path

import typer
from rich.markup import escape
from rich.table import Table

from kairos.cli.errors import cli_command, console
from kairos.services.context import RuntimeContext
from kairos.services.doctor import run_doctor


@cli_command
def run() -> None:
    ctx = RuntimeContext.open(Path.cwd())
    report = run_doctor(ctx)

    table = Table(title="kairos doctor")
    table.add_column("check")
    table.add_column("status")
    table.add_column("detail")

    for check in report.checks:
        status = "[green]ok[/green]" if check.ok else "[red]FAIL[/red]"
        table.add_row(check.name, status, escape(check.detail))

    console.print(table)

    if not report.healthy:
        # A failing doctor check is a workspace/integrity-category failure
        # (broken schema, tampered content, drifted search index) — never a
        # user-input mistake — so it gets code 2, not the generic 1. See
        # docs/cli.md's exit-code table.
        raise typer.Exit(code=2)
