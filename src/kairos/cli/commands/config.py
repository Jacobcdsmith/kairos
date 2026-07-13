"""``kairos config <symbol>``"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.panel import Panel

from kairos.cli.citation import provenance_lines
from kairos.cli.errors import cli_command, console
from kairos.services.config_query import get_config_symbol
from kairos.services.context import RuntimeContext


@cli_command
def run(
    symbol: Annotated[str, typer.Argument(help="Kconfig symbol name, e.g. CONFIG_WIFI.")],
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    result = get_config_symbol(ctx, symbol)

    body = (
        f"prompt: {result.prompt or '(none)'}\n"
        f"type: {result.symbol_type or '(none)'}\n"
        f"default: {result.default or '(none)'}\n"
        f"depends_on: {result.depends_on or '(none)'}\n"
        f"choices: {', '.join(result.choices) or '(none)'}\n"
        f"children: {', '.join(result.children) or '(none)'}\n"
        f"{provenance_lines(result.provenance)}"
    )
    console.print(Panel(escape(body), title=escape(result.symbol)))
