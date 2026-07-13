"""Verify every parser's output actually matches what docs/relation-registry.md
claims: every relation is ``origin=derived`` with a non-empty derivation
rule, and every predicate the registry says is evidenced actually carries
an ``evidence_span_id``. This is what keeps the registry from silently
drifting out of sync with the code it documents.
"""

from __future__ import annotations

from pathlib import Path

from kairos.domain.enums import Origin
from kairos.domain.parser import ParseResult
from kairos.infrastructure.parsers.json_parser import JsonParser
from kairos.infrastructure.parsers.kconfig import KconfigParser
from kairos.infrastructure.parsers.logs import LogParser
from kairos.infrastructure.parsers.pdf import PdfParser
from kairos.infrastructure.parsers.repository_files import PythonParser
from kairos.infrastructure.parsers.text_markdown import MarkdownParser

FIXTURES = Path(__file__).parent.parent / "fixtures"

# Predicates docs/relation-registry.md guarantees always carry an evidence span.
_EVIDENCED_PREDICATES = {
    "heading_contains",
    "json_contains",
    "menu_contains",
    "log_in_session",
    "imports",
}
# Predicates the registry documents as evidence-free by design (the relation
# itself is the evidence — physical sequence, or an entity-to-entity link
# whose citation lives on the owning span's metadata instead).
_UNEVIDENCED_PREDICATES = {"page_precedes", "depends_on"}


def _assert_registry_holds(result: ParseResult) -> None:
    for relation in result.relations:
        assert relation.origin == Origin.DERIVED, (
            f"{relation.predicate} must be origin=derived, got {relation.origin}"
        )
        assert relation.derivation_rule, f"{relation.predicate} must carry a derivation_rule"
        assert relation.predicate in _EVIDENCED_PREDICATES | _UNEVIDENCED_PREDICATES, (
            f"{relation.predicate} is not documented in docs/relation-registry.md"
        )
        if relation.predicate in _EVIDENCED_PREDICATES:
            assert relation.evidence_span_id is not None, (
                f"{relation.predicate} is documented as evidenced but has no evidence_span_id"
            )


def test_markdown_relations_match_registry() -> None:
    result = MarkdownParser().parse(FIXTURES / "text" / "sample.md", "artifact-md")
    assert result.relations  # sanity: this fixture actually exercises the predicate
    _assert_registry_holds(result)


def test_json_relations_match_registry() -> None:
    result = JsonParser().parse(FIXTURES / "json" / "sample.json", "artifact-json")
    assert result.relations
    _assert_registry_holds(result)


def test_kconfig_relations_match_registry() -> None:
    result = KconfigParser().parse(FIXTURES / "kconfig" / "sample_menu.json", "artifact-kconfig")
    assert result.relations
    _assert_registry_holds(result)


def test_logs_relations_match_registry() -> None:
    result = LogParser().parse(FIXTURES / "logs" / "sample.log", "artifact-log")
    assert result.relations
    _assert_registry_holds(result)


def test_repository_relations_match_registry() -> None:
    result = PythonParser().parse(FIXTURES / "repo" / "sample.py", "artifact-py")
    assert result.relations
    _assert_registry_holds(result)


def test_pdf_relations_match_registry() -> None:
    result = PdfParser().parse(FIXTURES / "pdf" / "sample.pdf", "artifact-pdf")
    assert result.relations
    _assert_registry_holds(result)
