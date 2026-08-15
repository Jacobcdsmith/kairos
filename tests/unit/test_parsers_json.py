"""JSON parser: json-path spans, tree containment relations, malformed input."""

from __future__ import annotations

import json
from pathlib import Path

from kairos.domain.enums import ParseStatus, SpanKind
from kairos.infrastructure.parsers.json_parser import JsonParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "json"


def test_json_indexes_every_scalar_at_json_path() -> None:
    parser = JsonParser()
    result = parser.parse(FIXTURES / "sample.json", "artifact-json")

    assert result.parse_status == ParseStatus.OK
    scalar_paths = {
        s.locator_json["json_path"]
        for s in result.spans
        if s.span_kind == SpanKind.JSON_SCALAR
    }
    assert "$.name" in scalar_paths
    assert "$.widgets[0].id" in scalar_paths
    assert "$.widgets[1].kind" in scalar_paths


def test_json_emits_containment_relations() -> None:
    parser = JsonParser()
    result = parser.parse(FIXTURES / "sample.json", "artifact-json")

    relations = [r for r in result.relations if r.predicate == "json_contains"]
    assert relations
    assert all(r.subject_kind == "span" and r.object_kind == "span" for r in relations)


def test_malformed_json_is_not_silently_dropped(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"a": 1,}', encoding="utf-8")  # trailing comma

    parser = JsonParser()
    result = parser.parse(bad, "artifact-bad")

    assert result.parse_status == ParseStatus.FAILED
    assert result.diagnostics
    assert len(result.spans) == 1
    assert '"a": 1' in result.spans[0].text_content


def test_json_deeply_nested_does_not_raise(tmp_path: Path) -> None:
    """A JSON document with >1000 levels of nesting must parse without
    RecursionError — the iterative traversal replaces the former recursive
    visit() closure that hit Python's default stack limit at ~950 levels."""
    depth = 1100
    # Build {"a": {"a": {"a": ... }}} depth levels deep
    doc: object = "leaf"
    for _ in range(depth):
        doc = {"a": doc}
    path = tmp_path / "deep.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    parser = JsonParser()
    result = parser.parse(path, "artifact-deep")

    assert result.parse_status == ParseStatus.OK
    # 1100 nested dict containers + 1 scalar leaf = depth + 1 spans
    # 1100 json_contains relations (one per container-to-child edge)
    assert len(result.spans) == depth + 1
    assert len(result.relations) == depth
