"""Uniform error-to-exit-code mapping. Every command's failure path goes through this."""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

import typer
from rich.console import Console
from rich.markup import escape

from kairos.domain.errors import KairosError

# IDs in this tool are full UUID4 hex strings, and every result must expose
# them (per the provenance requirement) — Rich's default 80-column fallback
# for non-TTY output (piped, redirected, or under test) would silently
# ellide or word-wrap them mid-table. There's no real "screen width" to
# respect for piped/redirected/captured output in the first place (a real
# terminal still gets its own actual width via the ``is_terminal`` check
# below), so non-TTY output uses a generous fixed width instead of guessing
# how many columns any given command will ever render.
_MIN_WIDTH = 2000


def _make_console(*, stderr: bool = False) -> Console:
    probe = Console(stderr=stderr)
    return probe if probe.is_terminal else Console(stderr=stderr, width=_MIN_WIDTH)


console = _make_console()
error_console = _make_console(stderr=True)


def cli_command[**P, R](func: Callable[P, R]) -> Callable[P, R]:
    """Catch ``KairosError`` (and only that — anything else is a real bug and
    should show a full traceback) and turn it into a clean message plus a
    non-zero exit code, per "every command returns non-zero on failure with
    an actionable error."
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except KairosError as exc:
            error_console.print(f"[bold red]Error:[/bold red] {escape(str(exc))}")
            raise typer.Exit(code=1) from exc

    return wrapper
