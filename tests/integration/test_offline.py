"""Offline/local-only guarantee: no command may touch the network.

Blocks every common network entry point at the socket layer, then drives
the full CLI surface (init, ingest of all six fixture kinds, artifacts,
show, search, trace, config, logs, note, well, doctor) through in-process.
If anything under ``src/kairos`` ever tries to open a socket, resolve a
hostname, or connect out, this test fails loudly instead of the guarantee
silently rotting.
"""

from __future__ import annotations

import socket
import sqlite3
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from tests.integration.conftest import FIXTURES, run_in


def _blocked(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("KAIROS attempted network access, which v0.1 must never do.")


@pytest.fixture(autouse=True)
def block_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "socket", _blocked)
    monkeypatch.setattr(socket, "create_connection", _blocked)
    monkeypatch.setattr(socket, "getaddrinfo", _blocked)


def _first_artifact_id(workspace: Path) -> str:
    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    try:
        row = conn.execute("SELECT id FROM artifacts WHERE kind = 'markdown' LIMIT 1").fetchone()
        return cast(str, row[0])
    finally:
        conn.close()


def test_full_command_surface_works_with_network_disabled(
    runner: CliRunner, workspace: Path
) -> None:
    for path in [
        FIXTURES / "text" / "sample.md",
        FIXTURES / "text" / "sample2.md",
        FIXTURES / "json" / "sample.json",
        FIXTURES / "kconfig" / "sample_menu.json",
        FIXTURES / "logs" / "sample.log",
        FIXTURES / "repo" / "sample.py",
        FIXTURES / "pdf" / "sample.pdf",
    ]:
        result = run_in(runner, workspace, ["ingest", str(path)])
        assert result.exit_code == 0, f"{path}: {result.output}"

    assert run_in(runner, workspace, ["artifacts"]).exit_code == 0

    artifact_id = _first_artifact_id(workspace)
    assert run_in(runner, workspace, ["show", artifact_id]).exit_code == 0
    assert run_in(runner, workspace, ["search", "widget"]).exit_code == 0
    assert run_in(runner, workspace, ["trace", "Widgets", "--depth", "2"]).exit_code == 0
    assert run_in(runner, workspace, ["config", "CONFIG_WIFI_POWER_SAVE"]).exit_code == 0
    assert run_in(runner, workspace, ["logs", "widget"]).exit_code == 0

    note_result = run_in(runner, workspace, ["note", "add", artifact_id, "offline test note"])
    assert note_result.exit_code == 0
    assert run_in(runner, workspace, ["note", "list", artifact_id]).exit_code == 0

    assert (
        run_in(
            runner, workspace, ["well", "create", "offline-well", "--purpose", "offline test"]
        ).exit_code
        == 0
    )
    assert run_in(runner, workspace, ["well", "add", "offline-well", artifact_id]).exit_code == 0
    assert run_in(runner, workspace, ["well", "show", "offline-well"]).exit_code == 0
    assert run_in(runner, workspace, ["well", "list"]).exit_code == 0

    assert run_in(runner, workspace, ["doctor"]).exit_code == 0
