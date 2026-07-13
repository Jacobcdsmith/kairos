"""PDF parser.

One span per page, holding that page's extracted text. Pages with no
extractable text (scanned images, blank pages) still get a span — empty
``text_content`` plus a diagnostic — never dropped. Consecutive pages are
linked by a ``page_precedes`` derived relation, letting ``trace`` walk
through a document page by page.
"""

from __future__ import annotations

from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from kairos.domain.enums import ArtifactKind, Origin, ParseStatus, RelationPredicate, SpanKind
from kairos.domain.ids import new_id
from kairos.domain.locators import PdfPageLocator, locator_to_json
from kairos.domain.models import Diagnostic, Relation, SourceSpan
from kairos.domain.parser import ParseResult

_PDF_MAGIC = b"%PDF-"


class PdfParser:
    kind = ArtifactKind.PDF
    parser_name = "kairos.pdf"
    parser_version = "1.0.0"

    def sniff(self, path: Path) -> bool:
        if path.suffix.lower() == ".pdf":
            return True
        try:
            with path.open("rb") as f:
                return f.read(len(_PDF_MAGIC)) == _PDF_MAGIC
        except OSError:
            return False

    def parse(self, path: Path, artifact_id: str) -> ParseResult:
        result = ParseResult()

        try:
            reader = PdfReader(str(path))
            pages = reader.pages
        except (PdfReadError, OSError) as exc:
            fallback_span_id = new_id()
            result.spans.append(
                SourceSpan(
                    id=fallback_span_id,
                    artifact_id=artifact_id,
                    span_kind=SpanKind.PDF_PAGE,
                    locator_json=locator_to_json(PdfPageLocator(page=0)),
                    parent_span_id=None,
                    ordinal=0,
                    text_content="",
                )
            )
            result.diagnostics.append(Diagnostic(message=f"Could not read PDF: {exc}"))
            result.parse_status = ParseStatus.FAILED
            return result

        any_missing_text = False
        previous_span_id: str | None = None

        for i, page in enumerate(pages):
            page_number = i + 1
            try:
                text_content = page.extract_text() or ""
            except Exception as exc:  # pypdf can raise various parse errors per page
                text_content = ""
                result.diagnostics.append(
                    Diagnostic(
                        message=f"Could not extract text from page {page_number}: {exc}",
                        locator_json=locator_to_json(PdfPageLocator(page=page_number)),
                    )
                )
                any_missing_text = True
            else:
                if not text_content.strip():
                    any_missing_text = True
                    result.diagnostics.append(
                        Diagnostic(
                            message=f"Page {page_number} has no extractable text",
                            locator_json=locator_to_json(PdfPageLocator(page=page_number)),
                        )
                    )

            span_id = new_id()
            result.spans.append(
                SourceSpan(
                    id=span_id,
                    artifact_id=artifact_id,
                    span_kind=SpanKind.PDF_PAGE,
                    locator_json=locator_to_json(PdfPageLocator(page=page_number)),
                    parent_span_id=None,
                    ordinal=i,
                    text_content=text_content,
                )
            )

            if previous_span_id is not None:
                result.relations.append(
                    Relation(
                        id=new_id(),
                        subject_id=previous_span_id,
                        subject_kind="span",
                        predicate=RelationPredicate.PAGE_PRECEDES.value,
                        object_id=span_id,
                        object_kind="span",
                        evidence_span_id=None,
                        origin=Origin.DERIVED,
                        derivation_rule="pdf.page_sequence.v1",
                        confidence=1.0,
                    )
                )
            previous_span_id = span_id

        result.parse_status = ParseStatus.PARTIAL if any_missing_text else ParseStatus.OK
        return result
