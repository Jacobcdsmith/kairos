"""``kairos --version`` — must agree with the installed package metadata,
the single source of truth (pyproject.toml's [project] version).
"""

from __future__ import annotations

from importlib.metadata import version as pkg_version

from typer.testing import CliRunner

from kairos import __version__
from kairos.cli.main import app


def test_version_flag_matches_package_metadata(runner: CliRunner) -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    installed_version = pkg_version("kairos")
    assert installed_version in result.output
    assert __version__ == installed_version


def test_version_flag_does_not_require_a_workspace(runner: CliRunner) -> None:
    # --version must work even outside any KAIROS workspace.
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0


def test_no_args_still_shows_help(runner: CliRunner) -> None:
    result = runner.invoke(app, [])
    assert "Usage:" in result.output
