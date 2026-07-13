"""Uniform error-to-exit-code mapping. Every command's failure path goes through this.

Exit code taxonomy (documented in docs/cli.md):
    0 - success
    1 - expected user/input/domain failure (KairosError, default exit_code)
    2 - workspace/configuration/integrity failure (KairosError subclasses
        that override exit_code — see kairos/domain/errors.py)
    3 - unexpected internal error (anything that is not a KairosError at all)
"""

from __future__ import annotations

import os
from collections.abc import Callable
from functools import wraps

import typer
from rich.console import Console
from rich.markup import escape

from kairos.domain.errors import KairosError

_DEBUG_ENV_VAR = "KAIROS_DEBUG"

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
    """Turn any failure into a clean message plus a non-zero exit code, per
    "every command returns non-zero on failure with an actionable error" —
    never a bare traceback, unless ``KAIROS_DEBUG`` is set.

    ``KairosError`` (an expected, actionable failure) exits with its own
    ``exit_code`` (1 or 2 — see kairos/domain/errors.py) and a one-line
    message. Anything else is a real bug: it exits 3 with a short, generic
    message, and the traceback is suppressed unless ``KAIROS_DEBUG`` is set
    to a non-empty value, in which case the original exception propagates
    unchanged.
    """

    @wraps(func)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        try:
            return func(*args, **kwargs)
        except KairosError as exc:
            error_console.print(f"[bold red]Error:[/bold red] {escape(str(exc))}")
            raise typer.Exit(code=exc.exit_code) from exc
        except typer.Exit:
            raise
        except Exception as exc:
            if os.environ.get(_DEBUG_ENV_VAR):
                raise
            error_console.print(
                f"[bold red]Error:[/bold red] an unexpected internal error occurred: "
                f"{escape(str(exc))}. Set {_DEBUG_ENV_VAR}=1 to see the full traceback."
            )
            raise typer.Exit(code=3) from exc

    return wrapper
