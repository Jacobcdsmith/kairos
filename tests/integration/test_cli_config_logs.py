"""``kairos config`` and ``kairos logs``."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from tests.integration.conftest import FIXTURES, run_in


def test_config_looks_up_kconfig_symbol(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "kconfig" / "sample_menu.json")])

    result = run_in(runner, workspace, ["config", "CONFIG_WIFI_POWER_SAVE"])
    assert result.exit_code == 0, result.output
    assert "WiFi power save" in result.output
    assert "CONFIG_WIFI" in result.output  # depends_on


def test_config_unknown_symbol_fails_cleanly(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "kconfig" / "sample_menu.json")])
    result = run_in(runner, workspace, ["config", "CONFIG_DOES_NOT_EXIST"])
    assert result.exit_code == 1


def test_logs_query_with_level_filter(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "logs" / "sample.log")])

    result = run_in(runner, workspace, ["logs", "connection", "--level", "ERROR"])
    assert result.exit_code == 0
    assert "ERROR" in result.output
    assert "dropped" in result.output


def test_logs_query_with_context_window(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "logs" / "sample.log")])

    result = run_in(runner, workspace, ["logs", "widget", "--before", "1", "--after", "1"])
    assert result.exit_code == 0
    assert "starting kernel" in result.output  # context line before the match
