"""PDF parser: per-page spans, blank-page diagnostics, page_precedes relation."""

from __future__ import annotations

from pathlib import Path

import pytest
from pypdf._page import PageObject

from kairos.domain.enums import ParseStatus, SpanKind
from kairos.infrastructure.parsers.pdf import PdfParser

FIXTURES = Path(__file__).parent.parent / "fixtures" / "pdf"


def test_pdf_extracts_text_per_page() -> None:
    parser = PdfParser()
    result = parser.parse(FIXTURES / "sample.pdf", "artifact-pdf")

    pages = [s for s in result.spans if s.span_kind == SpanKind.PDF_PAGE]
    assert len(pages) == 2
    assert "Hello Kairos" in pages[0].text_content


def test_blank_page_is_recorded_not_dropped() -> None:
    parser = PdfParser()
    result = parser.parse(FIXTURES / "sample.pdf", "artifact-pdf")

    pages = [s for s in result.spans if s.span_kind == SpanKind.PDF_PAGE]
    assert pages[1].text_content == ""
    assert result.parse_status == ParseStatus.PARTIAL
    assert any("no extractable text" in d.message for d in result.diagnostics)


def test_page_precedes_relation_links_consecutive_pages() -> None:
    parser = PdfParser()
    result = parser.parse(FIXTURES / "sample.pdf", "artifact-pdf")

    relations = [r for r in result.relations if r.predicate == "page_precedes"]
    assert len(relations) == 1
    pages = [s for s in result.spans if s.span_kind == SpanKind.PDF_PAGE]
    assert relations[0].subject_id == pages[0].id
    assert relations[0].object_id == pages[1].id


def test_extraction_failure_message_differs_from_blank_page_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page that legitimately has no text (a blank/image-only page) and a
    page where extraction itself raises are different failure modes and must
    say so — not collapse into one indistinguishable "no text" diagnostic.
    """

    def _raise(self: PageObject, *args: object, **kwargs: object) -> str:
        raise ValueError("simulated extraction failure")

    monkeypatch.setattr(PageObject, "extract_text", _raise)

    parser = PdfParser()
    result = parser.parse(FIXTURES / "sample.pdf", "artifact-pdf")

    assert result.parse_status == ParseStatus.PARTIAL
    assert any("Could not extract text from page" in d.message for d in result.diagnostics)
    assert not any("has no extractable text" in d.message for d in result.diagnostics)


def test_unreadable_pdf_is_not_dropped(tmp_path: Path) -> None:
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4\nnot a real pdf")

    parser = PdfParser()
    result = parser.parse(bad, "artifact-bad")

    assert result.parse_status == ParseStatus.FAILED
    assert result.diagnostics
    assert len(result.spans) == 1
