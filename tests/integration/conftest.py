"""Shared fixtures for CLI integration tests."""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from kairos.cli.main import app

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def workspace(tmp_path: Path, runner: CliRunner) -> Iterator[Path]:
    ws = tmp_path / "ws"
    result = runner.invoke(app, ["init", str(ws)])
    assert result.exit_code == 0, result.output
    yield ws


def run_in(runner: CliRunner, workspace: Path, args: list[str]) -> Result:
    """Invoke the CLI with the given workspace as the current working directory."""
    cwd = Path.cwd()
    try:
        os.chdir(workspace)
        return runner.invoke(app, args)
    finally:
        os.chdir(cwd)
