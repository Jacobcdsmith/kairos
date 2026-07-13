"""``kairos doctor``."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from tests.integration.conftest import run_in


def test_doctor_reports_healthy_on_a_fresh_workspace(runner: CliRunner, workspace: Path) -> None:
    result = run_in(runner, workspace, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "fts5_available" in result.output
    assert "schema_migration" in result.output
    assert "FAIL" not in result.output


def test_doctor_requires_a_workspace(runner: CliRunner, tmp_path: Path) -> None:
    result = run_in(runner, tmp_path, ["doctor"])
    assert result.exit_code == 1
