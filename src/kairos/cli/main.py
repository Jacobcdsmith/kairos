"""KAIROS CLI entry point. Assembles every command onto one Typer app."""

from __future__ import annotations

from typing import Annotated

import typer

from kairos import __version__
from kairos.cli.commands import (
    artifacts,
    config,
    doctor,
    ingest,
    init,
    logs,
    note,
    search,
    show,
    trace,
    tui,
    well,
)
from kairos.cli.errors import console

app = typer.Typer(
    name="kairos",
    help="KAIROS — a local-first, source-grounded workspace for a personal technical corpus.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)


def _version_callback(show_version: bool) -> None:
    if show_version:
        console.print(f"kairos {__version__}")
        raise typer.Exit()


@app.callback()
def main_callback(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            callback=_version_callback,
            is_eager=True,
            help="Show the installed KAIROS version and exit.",
        ),
    ] = False,
) -> None:
    return


app.command("init")(init.run)
app.command("ingest")(ingest.run)
app.command("artifacts")(artifacts.run)
app.command("show")(show.run)
app.command("search")(search.run)
app.command("trace")(trace.run)
app.command("config")(config.run)
app.command("logs")(logs.run)
app.command("doctor")(doctor.run)
app.command("tui")(tui.run)
app.add_typer(note.app, name="note")
app.add_typer(well.app, name="well")


if __name__ == "__main__":
    app()
