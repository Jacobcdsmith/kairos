"""Adversarial test for derived-relation discipline: two lexically similar
but textually distinct terms must never be linked by KAIROS. Entity
reconciliation is exact-match (canonical_name + entity_type), not fuzzy —
"Widget" and "Widgets" are different headings, different entities, and
``kairos trace`` must never produce an edge between them.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from typer.testing import CliRunner

from tests.integration.conftest import run_in


def test_lexically_similar_headings_are_not_reconciled(runner: CliRunner, workspace: Path) -> None:
    doc_a = workspace / "a.md"
    doc_b = workspace / "b.md"
    doc_a.write_text("# Widget\n\nSingular widget document.\n", encoding="utf-8")
    doc_b.write_text("# Widgets\n\nPlural widgets document.\n", encoding="utf-8")

    assert run_in(runner, workspace, ["ingest", str(doc_a)]).exit_code == 0
    assert run_in(runner, workspace, ["ingest", str(doc_b)]).exit_code == 0

    conn = sqlite3.connect(workspace / ".kairos" / "kairos.db")
    try:
        names = {
            cast(str, row[0])
            for row in conn.execute(
                "SELECT canonical_name FROM entities WHERE entity_type = 'heading'"
            ).fetchall()
        }
        assert names == {"Widget", "Widgets"}, "distinct headings must not reconcile to one entity"

        entity_ids = {
            row[0]: row[1]
            for row in conn.execute(
                "SELECT canonical_name, id FROM entities WHERE entity_type = 'heading'"
            ).fetchall()
        }
        widget_id = entity_ids["Widget"]
        widgets_id = entity_ids["Widgets"]

        linking_relations = conn.execute(
            "SELECT COUNT(*) FROM relations "
            "WHERE (subject_id = ? AND object_id = ?) OR (subject_id = ? AND object_id = ?)",
            (widget_id, widgets_id, widgets_id, widget_id),
        ).fetchone()[0]
        assert linking_relations == 0, "no relation may ever connect two distinct entities"
    finally:
        conn.close()

    # kairos trace on the singular term must never reach the plural document's
    # entity or spans via any edge (only via a direct FTS seed, which is
    # search, not an implied relation, and produces no edge at all).
    result = run_in(runner, workspace, ["trace", "Widget", "--depth", "5"])
    assert result.exit_code == 0
    assert "Plural widgets document" not in result.output
