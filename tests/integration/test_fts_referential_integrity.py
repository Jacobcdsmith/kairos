"""FTS5 correctness: ``source_spans_fts`` rows always map to a live
``source_spans.id``, and if something bypasses the sync triggers (only
possible via direct SQL — there is no ORM path to the virtual table), both
``kairos search`` and ``kairos doctor`` must notice.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from tests.integration.conftest import FIXTURES, run_in


def test_search_ignores_orphaned_fts_rows_and_doctor_flags_them(
    runner: CliRunner, workspace: Path
) -> None:
    result = run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    assert result.exit_code == 0, result.output

    healthy = run_in(runner, workspace, ["doctor"])
    assert healthy.exit_code == 0
    assert "fts_consistency" in healthy.output
    assert "FAIL" not in healthy.output

    # Defeat the trigger-enforced sync the only way possible: raw SQL
    # directly against the virtual table, bypassing every code path KAIROS
    # itself ever uses.
    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    try:
        conn.execute(
            "INSERT INTO source_spans_fts(rowid, text_content, span_id, artifact_id, span_kind) "
            "VALUES (999999, 'bogus orphaned widget text', 'no-such-span-id', "
            "'no-such-artifact-id', 'paragraph')"
        )
        conn.commit()
    finally:
        conn.close()

    search_result = run_in(runner, workspace, ["search", "bogus"])
    assert search_result.exit_code == 0
    assert "no-such-span-id" not in search_result.output
    assert "No matches" in search_result.output or "bogus" not in search_result.output.lower()

    corrupted = run_in(runner, workspace, ["doctor"])
    assert corrupted.exit_code == 2
    assert "fts_consistency" in corrupted.output
    assert "FAIL" in corrupted.output
