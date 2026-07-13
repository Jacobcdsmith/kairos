"""Python AST parser: module/class/function spans, entities, imports, syntax errors."""

from __future__ import annotations

from pathlib import Path

from kairos.domain.enums import EntityType, ParseStatus, SpanKind
from kairos.domain.locators import RepoFileLinesLocator, locator_from_json
from kairos.infrastructure.parsers.repository_files import PythonParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "repo"


def test_module_class_function_spans() -> None:
    parser = PythonParser()
    result = parser.parse(FIXTURES / "sample.py", "artifact-py")

    kinds = {s.span_kind for s in result.spans}
    assert SpanKind.MODULE in kinds
    assert SpanKind.CLASS_DEF in kinds
    assert SpanKind.FUNCTION_DEF in kinds
    assert result.parse_status == ParseStatus.OK

    class_span = next(s for s in result.spans if s.span_kind == SpanKind.CLASS_DEF)
    locator = locator_from_json(class_span.locator_json)
    assert isinstance(locator, RepoFileLinesLocator)
    assert locator.file_path.endswith("sample.py")


def test_entities_for_module_class_function() -> None:
    parser = PythonParser()
    result = parser.parse(FIXTURES / "sample.py", "artifact-py")

    names_by_type: dict[str, set[str]] = {}
    for e in result.entities:
        names_by_type.setdefault(e.entity_type, set()).add(e.canonical_name)

    assert "sample" in names_by_type[EntityType.MODULE.value]
    assert "Widget" in names_by_type[EntityType.CLASS_DEF.value]
    assert "render" in names_by_type[EntityType.FUNCTION_DEF.value]
    assert "build_widget" in names_by_type[EntityType.FUNCTION_DEF.value]


def test_imports_emit_derived_relations() -> None:
    parser = PythonParser()
    result = parser.parse(FIXTURES / "sample.py", "artifact-py")

    imports = [r for r in result.relations if r.predicate == "imports"]
    imported_names = {
        e.canonical_name
        for e in result.entities
        if e.entity_type == EntityType.MODULE.value and e.canonical_name != "sample"
    }
    assert imported_names == {"os", "collections"}
    assert len(imports) == 2
    assert all(r.subject_kind == "entity" and r.object_kind == "entity" for r in imports)


def test_entities_are_grounded_by_mentions() -> None:
    """Every extracted-layer entity needs an evidence trail: a Mention
    linking it back to the exact span it came from. The module, class, and
    function entities all get one, matching the pattern already established
    by the Markdown and Kconfig parsers (unresolved import-target entities
    are the one exception, by design — they aren't directly extracted here).
    """
    parser = PythonParser()
    result = parser.parse(FIXTURES / "sample.py", "artifact-py")

    directly_extracted_types = {
        EntityType.MODULE.value,
        EntityType.CLASS_DEF.value,
        EntityType.FUNCTION_DEF.value,
    }
    module_name = "sample"
    grounded_entities = [
        e
        for e in result.entities
        if e.entity_type in directly_extracted_types
        and not (e.entity_type == EntityType.MODULE.value and e.canonical_name != module_name)
    ]
    mentioned_entity_ids = {m.entity_id for m in result.mentions}
    for entity in grounded_entities:
        assert entity.id in mentioned_entity_ids, (
            f"{entity.entity_type} entity {entity.canonical_name!r} has no grounding mention"
        )


def test_syntax_error_is_not_dropped(tmp_path: Path) -> None:
    bad = tmp_path / "bad.py"
    bad.write_text("def broken(:\n    pass\n", encoding="utf-8")

    parser = PythonParser()
    result = parser.parse(bad, "artifact-bad")

    assert result.parse_status == ParseStatus.FAILED
    assert result.diagnostics
    assert len(result.spans) == 1
    assert "def broken" in result.spans[0].text_content
