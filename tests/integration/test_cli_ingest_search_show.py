"""End-to-end: init -> ingest -> artifacts -> show -> search, across parser kinds."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from tests.integration.conftest import FIXTURES, run_in


def test_ingest_artifacts_show_search_markdown(runner: CliRunner, workspace: Path) -> None:
    result = run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    assert result.exit_code == 0, result.output
    assert "markdown" in result.output

    result = run_in(runner, workspace, ["artifacts"])
    assert result.exit_code == 0
    assert "markdown" in result.output

    # pull the artifact id out of the database directly, since the table
    # output can wrap/truncate at narrow widths
    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    row = conn.execute("SELECT id FROM artifacts LIMIT 1").fetchone()
    artifact_id = cast(str, row[0])
    conn.close()

    result = run_in(runner, workspace, ["show", artifact_id])
    assert result.exit_code == 0
    assert "Widgets" in result.output

    result = run_in(runner, workspace, ["search", "widget"])
    assert result.exit_code == 0
    assert "extracted" in result.output


def test_ingest_is_idempotent_on_same_content(runner: CliRunner, workspace: Path) -> None:
    path = str(FIXTURES / "text" / "sample.md")
    first = run_in(runner, workspace, ["ingest", path])
    assert first.exit_code == 0
    second = run_in(runner, workspace, ["ingest", path])
    assert second.exit_code == 0
    assert "already" in second.output.lower()


def test_ingest_all_six_parser_kinds(runner: CliRunner, workspace: Path) -> None:
    paths = [
        FIXTURES / "text" / "sample.md",
        FIXTURES / "json" / "sample.json",
        FIXTURES / "kconfig" / "sample_menu.json",
        FIXTURES / "logs" / "sample.log",
        FIXTURES / "repo" / "sample.py",
        FIXTURES / "pdf" / "sample.pdf",
    ]
    for path in paths:
        result = run_in(runner, workspace, ["ingest", str(path)])
        assert result.exit_code == 0, f"{path}: {result.output}"

    result = run_in(runner, workspace, ["artifacts", "--limit", "10"])
    assert result.exit_code == 0
    for kind in ["markdown", "json", "kconfig", "log", "repository_file", "pdf"]:
        assert kind in result.output


def test_show_unknown_artifact_id_fails_cleanly(runner: CliRunner, workspace: Path) -> None:
    result = run_in(runner, workspace, ["show", "does-not-exist"])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_ingest_nonexistent_path_fails_cleanly(runner: CliRunner, workspace: Path) -> None:
    result = run_in(runner, workspace, ["ingest", "/no/such/path"])
    assert result.exit_code == 1


def test_search_malformed_fts_query_fails_cleanly(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    result = run_in(runner, workspace, ["search", "widget()"])
    assert result.exit_code == 1
    assert "Error" in result.output


def test_commands_require_a_workspace(runner: CliRunner, tmp_path: Path) -> None:
    result = run_in(runner, tmp_path, ["artifacts"])
    assert result.exit_code == 1
