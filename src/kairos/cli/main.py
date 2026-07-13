"""KAIROS CLI entry point. Assembles every command onto one Typer app."""

from __future__ import annotations

import typer

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
    well,
)

app = typer.Typer(
    name="kairos",
    help="KAIROS — a local-first, source-grounded workspace for a personal technical corpus.",
    no_args_is_help=True,
    pretty_exceptions_show_locals=False,
)

app.command("init")(init.run)
app.command("ingest")(ingest.run)
app.command("artifacts")(artifacts.run)
app.command("show")(show.run)
app.command("search")(search.run)
app.command("trace")(trace.run)
app.command("config")(config.run)
app.command("logs")(logs.run)
app.command("doctor")(doctor.run)
app.add_typer(note.app, name="note")
app.add_typer(well.app, name="well")


if __name__ == "__main__":
    app()
