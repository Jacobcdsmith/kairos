"""Text/Markdown parser: spans, heading tree, derived relations, diagnostics."""

from __future__ import annotations

from pathlib import Path

from kairos.domain.enums import ParseStatus, SpanKind
from kairos.infrastructure.parsers.text_markdown import MarkdownParser, TextParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "text"


def test_markdown_parses_headings_paragraphs_code_links() -> None:
    parser = MarkdownParser()
    result = parser.parse(FIXTURES / "sample.md", "artifact-1")

    kinds = [s.span_kind for s in result.spans]
    assert kinds.count(SpanKind.HEADING) == 2
    assert SpanKind.PARAGRAPH in kinds
    assert SpanKind.CODE_BLOCK in kinds
    assert SpanKind.LINK in kinds
    assert result.parse_status == ParseStatus.OK

    link_span = next(s for s in result.spans if s.span_kind == SpanKind.LINK)
    assert link_span.text_content == "the spec"
    assert link_span.metadata["url"] == "https://example.com/spec"


def test_markdown_emits_heading_contains_relations_and_entities() -> None:
    parser = MarkdownParser()
    result = parser.parse(FIXTURES / "sample.md", "artifact-1")

    assert len(result.entities) == 2  # Widgets, Details
    assert {e.canonical_name for e in result.entities} == {"Widgets", "Details"}
    relations = [r for r in result.relations if r.predicate == "heading_contains"]
    assert len(relations) >= 2
    assert all(r.subject_kind == "entity" and r.object_kind == "span" for r in relations)

    # every heading is also mentioned (self-grounding, used by cross-doc trace)
    assert len(result.mentions) == 2


def test_markdown_nests_child_spans_under_nearest_heading() -> None:
    parser = MarkdownParser()
    result = parser.parse(FIXTURES / "sample.md", "artifact-1")

    headings = {s.text_content: s.id for s in result.spans if s.span_kind == SpanKind.HEADING}
    details_paragraph = next(
        s for s in result.spans if s.span_kind == SpanKind.PARAGRAPH and "spec" in s.text_content
    )
    assert details_paragraph.parent_span_id == headings["Details"]


def test_markdown_unclosed_fence_is_partial_not_dropped(tmp_path: Path) -> None:
    bad = tmp_path / "bad.md"
    bad.write_text("# Title\n\n```python\ndef f():\n    pass\n", encoding="utf-8")

    parser = MarkdownParser()
    result = parser.parse(bad, "artifact-bad")

    assert result.parse_status == ParseStatus.PARTIAL
    assert result.diagnostics
    code_spans = [s for s in result.spans if s.span_kind == SpanKind.CODE_BLOCK]
    assert len(code_spans) == 1
    assert "def f()" in code_spans[0].text_content


def test_plain_text_has_no_headings() -> None:
    parser = TextParser()
    result = parser.parse(FIXTURES / "sample.txt", "artifact-2")

    assert all(s.span_kind == SpanKind.PARAGRAPH for s in result.spans)
    assert len(result.spans) == 2
    assert result.parse_status == ParseStatus.OK
