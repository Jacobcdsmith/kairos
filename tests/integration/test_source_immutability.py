"""Source immutability: KAIROS must never mutate a registered source file,
and ``kairos doctor`` must notice if a stored content-addressed blob is
tampered with after ingest.
"""

from __future__ import annotations

import hashlib
import sqlite3
import stat
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from tests.integration.conftest import FIXTURES, run_in

_FIXTURE_PATHS = [
    FIXTURES / "text" / "sample.md",
    FIXTURES / "text" / "sample2.md",
    FIXTURES / "json" / "sample.json",
    FIXTURES / "kconfig" / "sample_menu.json",
    FIXTURES / "logs" / "sample.log",
    FIXTURES / "repo" / "sample.py",
    FIXTURES / "pdf" / "sample.pdf",
]


def _fingerprint(paths: list[Path]) -> dict[Path, tuple[str, int]]:
    prints: dict[Path, tuple[str, int]] = {}
    for path in paths:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        prints[path] = (digest, path.stat().st_mtime_ns)
    return prints


def _first_artifact_id(workspace: Path) -> str:
    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    try:
        row = conn.execute("SELECT id FROM artifacts WHERE kind = 'markdown' LIMIT 1").fetchone()
        return cast(str, row[0])
    finally:
        conn.close()


def test_full_command_surface_never_mutates_source_files(
    runner: CliRunner, workspace: Path
) -> None:
    before = _fingerprint(_FIXTURE_PATHS)

    for path in _FIXTURE_PATHS:
        result = run_in(runner, workspace, ["ingest", str(path)])
        assert result.exit_code == 0, f"{path}: {result.output}"

    artifact_id = _first_artifact_id(workspace)
    run_in(runner, workspace, ["artifacts"])
    run_in(runner, workspace, ["show", artifact_id])
    run_in(runner, workspace, ["search", "widget"])
    run_in(runner, workspace, ["trace", "Widgets", "--depth", "2"])
    run_in(runner, workspace, ["config", "CONFIG_WIFI_POWER_SAVE"])
    run_in(runner, workspace, ["logs", "widget"])
    run_in(runner, workspace, ["note", "add", artifact_id, "note"])
    run_in(runner, workspace, ["note", "list", artifact_id])
    run_in(runner, workspace, ["well", "create", "w", "--purpose", "p"])
    run_in(runner, workspace, ["well", "add", "w", artifact_id])
    run_in(runner, workspace, ["well", "show", "w"])
    run_in(runner, workspace, ["well", "list"])
    run_in(runner, workspace, ["doctor"])

    after = _fingerprint(_FIXTURE_PATHS)
    assert before == after, "a registered source file's bytes or mtime changed"


def test_doctor_detects_a_corrupted_content_blob(runner: CliRunner, workspace: Path) -> None:
    md_path = FIXTURES / "text" / "sample.md"
    result = run_in(runner, workspace, ["ingest", str(md_path)])
    assert result.exit_code == 0, result.output

    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    try:
        sha256 = cast(
            str,
            conn.execute("SELECT sha256 FROM artifacts WHERE kind = 'markdown' LIMIT 1").fetchone()[
                0
            ],
        )
    finally:
        conn.close()

    healthy = run_in(runner, workspace, ["doctor"])
    assert healthy.exit_code == 0
    assert "content_integrity" in healthy.output
    assert "FAIL" not in healthy.output

    blob_path = workspace / ".kairos" / "content" / sha256[:2] / sha256
    blob_path.chmod(stat.S_IWRITE | stat.S_IREAD)
    data = bytearray(blob_path.read_bytes())
    data[0] ^= 0xFF
    blob_path.write_bytes(bytes(data))
    blob_path.chmod(stat.S_IREAD)

    corrupted = run_in(runner, workspace, ["doctor"])
    assert corrupted.exit_code == 2
    assert "content_integrity" in corrupted.output
    assert "FAIL" in corrupted.output
