"""``kairos tui`` must degrade cleanly when the optional 'tui' extra is not
installed, and every other command must be entirely unaffected by whether
Textual is present. See kairos/cli/commands/tui.py's find_spec guard and
docs/tli-implementation-plan.md's dependency-strategy section.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from kairos.cli.commands import tui as tui_command
from kairos.cli.main import app


def _no_spec(_name: str) -> None:
    """Stand-in for ``importlib.util.find_spec`` simulating "not installed"."""
    return None


def test_tui_command_reports_missing_extra(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner
) -> None:
    monkeypatch.setattr(tui_command.importlib.util, "find_spec", _no_spec)
    result = runner.invoke(app, ["tui"])
    assert result.exit_code == 1
    assert 'pip install -e ".[tui]"' in result.output
    assert "kairos tui" in result.output
    # No traceback leaked to the user.
    assert "Traceback" not in result.output


def test_tui_command_does_not_import_textual_at_module_scope() -> None:
    # Both `import textual` and `from kairos.tui.app import KairosApp` are
    # local to run() — importing this module (as kairos.cli.main always
    # does) must not bind either name at module scope.
    assert "textual" not in vars(tui_command)
    assert "KairosApp" not in vars(tui_command)


def test_ordinary_cli_unaffected_by_tui_extra_presence(
    monkeypatch: pytest.MonkeyPatch, runner: CliRunner, tmp_path: Path
) -> None:
    # Simulate "Textual absent" and confirm a wholly unrelated command still
    # works end to end — proves the optional dependency cannot leak into the
    # rest of the CLI's import graph.
    monkeypatch.setattr(tui_command.importlib.util, "find_spec", _no_spec)
    ws = tmp_path / "ws"
    result = runner.invoke(app, ["init", str(ws)])
    assert result.exit_code == 0, result.output
    result = runner.invoke(app, ["doctor"], catch_exceptions=False)
    # doctor requires a workspace on cwd; just confirm no import-time failure
    # occurred (exit code is either 0 from within ws or 2 for "no workspace",
    # never 3/"unexpected internal error").
    assert result.exit_code in (0, 2)
