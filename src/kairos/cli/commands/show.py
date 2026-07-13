"""``kairos show <artifact-id> [--locator <locator>]``"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.panel import Panel

from kairos.cli.errors import cli_command, console
from kairos.services.context import RuntimeContext
from kairos.services.show import show as show_service


@cli_command
def run(
    artifact_id: Annotated[str, typer.Argument(help="Artifact id, from `kairos artifacts`.")],
    locator: Annotated[
        str | None,
        typer.Option("--locator", help="Restrict to one locator, e.g. lines:1-1 or page:3."),
    ] = None,
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    detail = show_service(ctx, artifact_id, locator=locator)

    a = detail.artifact
    console.print(
        Panel(
            escape(
                f"id: {a.id}\n"
                f"path: {a.source_path}\n"
                f"kind: {a.kind}\n"
                f"parser: {a.parser_name} v{a.parser_version}\n"
                f"parse_status: {a.parse_status}\n"
                f"ingested_at: {a.ingested_at.isoformat(timespec='seconds')}"
            ),
            title="Artifact",
        )
    )

    for span in detail.spans:
        body = escape(span.text_content) if span.text_content else "[dim](empty)[/dim]"
        title = f"[{span.span_kind}] {span.provenance.locator_str}  layer={span.provenance.layer}"
        console.print(Panel(body, title=escape(title), subtitle=f"span_id={span.span_id}"))
