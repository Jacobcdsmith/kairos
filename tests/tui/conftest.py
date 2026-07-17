"""Shared fixtures for TUI tests: an ingested workspace built the same way
``tests/integration/conftest.py`` builds one for CLI tests (same fixture
files, same ``kairos init``/``ingest`` path), plus a ``RuntimeContext`` open
on it for controller-level tests that don't need the CLI at all.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner, Result

from kairos.cli.main import app
from kairos.services.context import RuntimeContext

FIXTURES = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def run_in(runner: CliRunner, workspace: Path, args: list[str]) -> Result:
    cwd = Path.cwd()
    try:
        os.chdir(workspace)
        return runner.invoke(app, args)
    finally:
        os.chdir(cwd)


@pytest.fixture
def ingested_workspace(tmp_path: Path, runner: CliRunner) -> Iterator[Path]:
    ws = tmp_path / "ws"
    result = runner.invoke(app, ["init", str(ws)])
    assert result.exit_code == 0, result.output

    ingest_paths = [
        FIXTURES / "text" / "sample.md",
        FIXTURES / "text" / "sample2.md",
        FIXTURES / "json" / "sample.json",
        FIXTURES / "kconfig" / "sample_menu.json",
        FIXTURES / "logs" / "sample.log",
        FIXTURES / "repo" / "sample.py",
        FIXTURES / "repo" / "consumer.py",
    ]
    for path in ingest_paths:
        result = run_in(runner, ws, ["ingest", str(path)])
        assert result.exit_code == 0, result.output

    yield ws


@pytest.fixture
def runtime_ctx(ingested_workspace: Path) -> RuntimeContext:
    return RuntimeContext.open(ingested_workspace)
