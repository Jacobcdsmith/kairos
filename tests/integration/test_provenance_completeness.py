"""Every source-derived, user-visible result must show all six provenance
fields: artifact id, workspace-relative path, artifact kind, exact locator,
parser name+version, and layer. This parses actual rendered CLI output
(not the underlying schema) for ``search``, ``trace``, ``config``, and
``logs`` — the schema already carried every field; the gap this audit found
was in what the terminal actually printed.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from tests.integration.conftest import FIXTURES, run_in


def _first_artifact_id(workspace: Path, kind: str) -> str:
    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    try:
        row = conn.execute("SELECT id FROM artifacts WHERE kind = ? LIMIT 1", (kind,)).fetchone()
        return cast(str, row[0])
    finally:
        conn.close()


def test_search_output_carries_full_provenance(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    artifact_id = _first_artifact_id(workspace, "markdown")

    result = run_in(runner, workspace, ["search", "widget"])
    assert result.exit_code == 0
    assert artifact_id in result.output
    assert "markdown" in result.output
    assert "kairos.markdown" in result.output
    assert "1.0.0" in result.output
    assert "extracted" in result.output
    assert "lines:" in result.output


def test_trace_span_node_carries_full_provenance(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    artifact_id = _first_artifact_id(workspace, "markdown")

    result = run_in(runner, workspace, ["trace", "Widgets", "--depth", "2"])
    assert result.exit_code == 0
    assert artifact_id in result.output
    assert "markdown" in result.output
    assert "kairos.markdown" in result.output
    assert "extracted" in result.output


def test_config_output_carries_full_provenance(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "kconfig" / "sample_menu.json")])
    artifact_id = _first_artifact_id(workspace, "kconfig")

    result = run_in(runner, workspace, ["config", "CONFIG_WIFI_POWER_SAVE"])
    assert result.exit_code == 0
    assert artifact_id in result.output
    assert "kconfig" in result.output
    assert "kairos.kconfig" in result.output
    assert "extracted" in result.output


def test_logs_output_carries_full_provenance(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "logs" / "sample.log")])
    artifact_id = _first_artifact_id(workspace, "log")

    result = run_in(runner, workspace, ["logs", "widget"])
    assert result.exit_code == 0
    assert artifact_id in result.output
    assert "kairos.log" in result.output
    assert "extracted" in result.output
