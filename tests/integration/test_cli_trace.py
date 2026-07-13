"""``kairos trace`` — evidence-first traversal, including the >=2-hop cross-artifact case."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from tests.integration.conftest import FIXTURES, run_in


def test_trace_by_entity_name_reaches_sibling_spans(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])

    result = run_in(runner, workspace, ["trace", "Widgets", "--depth", "2"])
    assert result.exit_code == 0
    assert "heading_contains" in result.output
    assert "extracted" in result.output
    # a span node must expose which artifact it came from, not just its own id
    assert "sample.md" in result.output


def test_trace_crosses_artifacts_via_shared_heading(runner: CliRunner, workspace: Path) -> None:
    """The headline scenario: a term with no entity of its own (inside a
    paragraph in one document) must reach a *different* document in a
    couple of hops, by climbing up to a heading entity the two documents
    share and back down — not by degenerating into plain search.
    """
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample2.md")])

    result = run_in(runner, workspace, ["trace", "gadgets", "--depth", "3"])
    assert result.exit_code == 0
    # the seed span (from sample2.md, mentioning "gadgets") and a sibling
    # span from sample.md (a different artifact) must both appear
    assert "widget system" in result.output.lower()
    assert "gadgets" in result.output.lower()
    # the two span nodes must be identifiable as coming from two distinct
    # artifacts, not just two distinct span ids
    assert "sample.md" in result.output
    assert "sample2.md" in result.output


def test_trace_unknown_term_reports_no_matches(runner: CliRunner, workspace: Path) -> None:
    run_in(runner, workspace, ["ingest", str(FIXTURES / "text" / "sample.md")])
    result = run_in(runner, workspace, ["trace", "nonexistenttermxyz"])
    assert result.exit_code == 0
    assert "No matches" in result.output
