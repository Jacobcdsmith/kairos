"""``kairos tui`` — launch the Terminal Lineage Interface (v0.2-alpha, optional).

Textual is an optional dependency (``pip install -e ".[tui]"``). This module
must never import ``textual`` — or anything under ``kairos.tui`` — at module
scope, since ``kairos.cli.main`` imports this module unconditionally to wire
up every command. The presence check uses ``importlib.util.find_spec``
rather than a bare ``try/except ImportError`` around the real import so the
"Textual is missing" path is exercised without needing to actually uninstall
Textual in a test process.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import typer

from kairos.cli.errors import cli_command, error_console

_INSTALL_MESSAGE = (
    "The Terminal Lineage Interface requires the optional 'tui' extra.\n"
    '  Install it with:  pip install -e ".[tui]"\n'
    "  Then run:         kairos tui"
)


@cli_command
def run() -> None:
    if importlib.util.find_spec("textual") is None:
        # markup=False: the install message contains a literal "[tui]", which
        # Rich would otherwise parse as a (nonexistent) style tag and silently
        # drop.
        error_console.print(_INSTALL_MESSAGE, markup=False)
        raise typer.Exit(code=1)

    from kairos.services.context import RuntimeContext
    from kairos.tui.app import KairosApp

    ctx = RuntimeContext.open(Path.cwd())
    KairosApp(ctx).run()
