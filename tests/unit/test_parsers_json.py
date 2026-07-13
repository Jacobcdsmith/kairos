"""JSON parser: json-path spans, tree containment relations, malformed input."""

from __future__ import annotations

from pathlib import Path

from kairos.domain.enums import ParseStatus, SpanKind
from kairos.infrastructure.parsers.json_parser import JsonParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "json"


def test_json_indexes_every_scalar_at_json_path() -> None:
    parser = JsonParser()
    result = parser.parse(FIXTURES / "sample.json", "artifact-json")

    assert result.parse_status == ParseStatus.OK
    scalar_paths = {
        s.locator_json["json_path"] for s in result.spans if s.span_kind == SpanKind.JSON_SCALAR
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
