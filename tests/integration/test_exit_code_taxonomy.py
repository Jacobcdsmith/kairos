"""The CLI failure contract's exit-code taxonomy (see docs/cli.md):
    0 - success
    1 - expected user/input/domain failure
    2 - workspace/configuration/integrity failure
    3 - unexpected internal error

One test per category, asserting the *exact* code (not just non-zero).
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

import pytest
from typer.testing import CliRunner

from tests.integration.conftest import FIXTURES, run_in


def _first_artifact_id(workspace: Path) -> str:
    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    try:
        row = conn.execute("SELECT id FROM artifacts LIMIT 1").fetchone()
        return cast(str, row[0])
    finally:
        conn.close()


def test_missing_workspace_is_code_2(runner: CliRunner, tmp_path: Path) -> None:
    result = run_in(runner, tmp_path, ["artifacts"])
    assert result.exit_code == 2


def test_init_on_existing_workspace_is_code_2(runner: CliRunner, workspace: Path) -> None:
    result = run_in(runner, workspace.parent, ["init", str(workspace)])
    assert result.exit_code == 2


def test_bad_artifact_id_is_code_1(runner: CliRunner, workspace: Path) -> None:
    result = run_in(runner, workspace, ["show", "does-not-exist"])
    assert result.exit_code == 1


def test_bad_locator_is_code_1(runner: CliRunner, workspace: Path) -> None:
    ingest_result = run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    assert ingest_result.exit_code == 0
    artifact_id = _first_artifact_id(workspace)

    result = run_in(runner, workspace, ["show", artifact_id, "--locator", "not-a-locator"])
    assert result.exit_code == 1


def test_unknown_kconfig_symbol_is_code_1(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "kconfig" / "sample_menu.json")])
    result = run_in(runner, workspace, ["config", "CONFIG_DOES_NOT_EXIST"])
    assert result.exit_code == 1


def test_unknown_well_is_code_1(runner: CliRunner, workspace: Path) -> None:
    result = run_in(runner, workspace, ["well", "show", "no-such-well"])
    assert result.exit_code == 1


def test_invalid_well_operation_is_code_1(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["well", "create", "dup", "--purpose", "x"])
    result = run_in(runner, workspace, ["well", "create", "dup", "--purpose", "y"])
    assert result.exit_code == 1


def test_failing_doctor_check_is_code_2(runner: CliRunner, workspace: Path) -> None:
    # Deleting the content directory breaks content_store/content_integrity —
    # a workspace/integrity failure, distinct from a user typo.
    (workspace / ".kairos" / "content").rmdir()
    result = run_in(runner, workspace, ["doctor"])
    assert result.exit_code == 2


def test_unexpected_internal_error_is_code_3(
    runner: CliRunner, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated unexpected bug")

    monkeypatch.setattr("kairos.cli.commands.artifacts.list_artifacts", _boom)
    result = run_in(runner, workspace, ["artifacts"])
    assert result.exit_code == 3
    assert "unexpected internal error" in result.output.lower()
    assert "Traceback" not in result.output


def test_unexpected_internal_error_shows_traceback_under_debug(
    runner: CliRunner, workspace: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("simulated unexpected bug")

    monkeypatch.setattr("kairos.cli.commands.artifacts.list_artifacts", _boom)
    monkeypatch.setenv("KAIROS_DEBUG", "1")
    result = run_in(runner, workspace, ["artifacts"])
    assert result.exit_code != 0
    assert result.exception is not None
