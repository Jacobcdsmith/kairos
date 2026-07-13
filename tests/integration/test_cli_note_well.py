"""``kairos note`` and ``kairos well`` command families."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from tests.integration.conftest import FIXTURES, run_in


def _first_artifact_id(workspace: Path) -> str:
    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    try:
        row = conn.execute("SELECT id FROM artifacts LIMIT 1").fetchone()
        return cast(str, row[0])
    finally:
        conn.close()


def _first_well_member_id(workspace: Path) -> str:
    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    try:
        row = conn.execute("SELECT id FROM well_members LIMIT 1").fetchone()
        return cast(str, row[0])
    finally:
        conn.close()


def test_note_add_and_list(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    artifact_id = _first_artifact_id(workspace)

    result = run_in(runner, workspace, ["note", "add", artifact_id, "revisit after v0.2"])
    assert result.exit_code == 0, result.output

    result = run_in(runner, workspace, ["note", "list", artifact_id])
    assert result.exit_code == 0
    assert "revisit after v0.2" in result.output


def test_note_add_on_unknown_target_fails(runner: CliRunner, workspace: Path) -> None:
    result = run_in(runner, workspace, ["note", "add", "does-not-exist", "text"])
    assert result.exit_code == 1


def test_well_create_add_show_remove_list(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    artifact_id = _first_artifact_id(workspace)

    result = run_in(
        runner, workspace, ["well", "create", "widget-work", "--purpose", "widget docs"]
    )
    assert result.exit_code == 0, result.output

    result = run_in(runner, workspace, ["well", "add", "widget-work", artifact_id])
    assert result.exit_code == 0, result.output

    result = run_in(runner, workspace, ["well", "show", "widget-work"])
    assert result.exit_code == 0
    assert artifact_id in result.output

    result = run_in(runner, workspace, ["well", "list"])
    assert result.exit_code == 0
    assert "widget-work" in result.output

    member_id = _first_well_member_id(workspace)

    result = run_in(runner, workspace, ["well", "remove", "widget-work", member_id])
    assert result.exit_code == 0, result.output

    result = run_in(runner, workspace, ["well", "show", "widget-work"])
    assert "0 members" in result.output.replace("\n", " ")


def test_well_create_duplicate_name_fails(runner: CliRunner, workspace: Path) -> None:
    result = run_in(runner, workspace, ["well", "create", "dup", "--purpose", "x"])
    assert result.exit_code == 0
    result = run_in(runner, workspace, ["well", "create", "dup", "--purpose", "y"])
    assert result.exit_code == 1


def test_search_scoped_to_well(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    artifact_id = _first_artifact_id(workspace)
    run_in(runner, workspace, ["well", "create", "scope-test", "--purpose", "x"])
    run_in(runner, workspace, ["well", "add", "scope-test", artifact_id])

    result = run_in(runner, workspace, ["search", "widget", "--well", "scope-test"])
    assert result.exit_code == 0
    assert "extracted" in result.output

    result = run_in(runner, workspace, ["search", "widget", "--well", "no-such-well"])
    assert result.exit_code == 1
