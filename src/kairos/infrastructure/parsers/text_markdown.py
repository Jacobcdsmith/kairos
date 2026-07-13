"""Plain text and Markdown parsers.

Extract headings, paragraphs, fenced code blocks, and links with line-range
locators. Headings become entities; every span nests under its nearest
enclosing heading via ``parent_span_id``. A ``heading_contains`` derived
relation links the heading entity to each direct child span, giving
``trace`` real edges instead of just a flat span list. Each heading is also
recorded as a ``mention`` of its own entity — the same heading text repeated
across artifacts resolves to the same entity (dedup happens in the ingest
service), which is what lets ``trace`` cross artifact boundaries.

Text and Markdown share the same line-oriented scanning logic; they differ
only in whether heading/fence/link syntax is recognized. Each artifact kind
gets its own thin ``Parser`` implementation (one ``kind`` per class, per the
shared protocol) delegating to ``_scan``.
"""

from __future__ import annotations

import re
from pathlib import Path

from kairos.domain.enums import (
    ArtifactKind,
    EntityType,
    Origin,
    ParseStatus,
    RelationPredicate,
    SpanKind,
)
from kairos.domain.ids import new_id
from kairos.domain.locators import LineRangeLocator, locator_to_json
from kairos.domain.models import Diagnostic, Entity, Mention, Relation, SourceSpan
from kairos.domain.parser import ParseResult

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
_FENCE_RE = re.compile(r"^```")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

MARKDOWN_EXTENSIONS = {".md", ".markdown"}
TEXT_EXTENSIONS = {".txt"}


def _scan(path: Path, artifact_id: str, *, is_markdown: bool) -> ParseResult:
    result = ParseResult()
    raw = path.read_bytes()
    text = raw.decode("utf-8", errors="replace")
    lines = text.splitlines()

    # heading_stack: list of (level, entity_id, span_id) from outermost to innermost
    heading_stack: list[tuple[int, str, str]] = []
    ordinal = 0
    i = 0
    n = len(lines)
    unclosed_fence = False

    def current_parent() -> str | None:
        return heading_stack[-1][2] if heading_stack else None

    def add_child_relation(span: SourceSpan) -> None:
        if not heading_stack:
            return
        _level, heading_entity_id, heading_span_id = heading_stack[-1]
        result.relations.append(
            Relation(
                id=new_id(),
                subject_id=heading_entity_id,
                subject_kind="entity",
                predicate=RelationPredicate.HEADING_CONTAINS.value,
                object_id=span.id,
                object_kind="span",
                evidence_span_id=heading_span_id,
                origin=Origin.DERIVED,
                derivation_rule="markdown.heading_containment.v1",
                confidence=1.0,
            )
        )

    while i < n:
        line = lines[i]

        if is_markdown and (m := _HEADING_RE.match(line)):
            level = len(m.group(1))
            heading_text = m.group(2).strip()
            span_id = new_id()
            locator = LineRangeLocator(start_line=i + 1, end_line=i + 1)
            span = SourceSpan(
                id=span_id,
                artifact_id=artifact_id,
                span_kind=SpanKind.HEADING,
                locator_json=locator_to_json(locator),
                parent_span_id=current_parent(),
                ordinal=ordinal,
                text_content=heading_text,
            )
            ordinal += 1
            result.spans.append(span)

            # pop stack down to this heading's level
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()

            entity_id = new_id()
            entity = Entity(
                id=entity_id,
                canonical_name=heading_text,
                entity_type=EntityType.HEADING.value,
                origin=Origin.EXTRACTED,
            )
            result.entities.append(entity)
            result.mentions.append(
                Mention(
                    id=new_id(),
                    entity_id=entity_id,
                    source_span_id=span_id,
                    surface_form=heading_text,
                    extraction_rule="markdown.heading.v1",
                    confidence=1.0,
                )
            )
            if heading_stack:
                add_child_relation(span)
            heading_stack.append((level, entity_id, span_id))
            i += 1
            continue

        if is_markdown and _FENCE_RE.match(line):
            start = i
            i += 1
            body_lines: list[str] = []
            closed = False
            while i < n:
                if _FENCE_RE.match(lines[i]):
                    closed = True
                    break
                body_lines.append(lines[i])
                i += 1
            end_line = i if closed else i - 1
            if not closed:
                unclosed_fence = True
                result.diagnostics.append(
                    Diagnostic(
                        message=f"Unclosed fenced code block starting at line {start + 1}",
                        severity="warning",
                        locator_json=locator_to_json(
                            LineRangeLocator(start_line=start + 1, end_line=end_line + 1)
                        ),
                    )
                )
            locator = LineRangeLocator(start_line=start + 1, end_line=end_line + 1)
            span = SourceSpan(
                id=new_id(),
                artifact_id=artifact_id,
                span_kind=SpanKind.CODE_BLOCK,
                locator_json=locator_to_json(locator),
                parent_span_id=current_parent(),
                ordinal=ordinal,
                text_content="\n".join(body_lines),
            )
            ordinal += 1
            result.spans.append(span)
            add_child_relation(span)
            if closed:
                i += 1
            continue

        if line.strip() == "":
            i += 1
            continue

        # paragraph: consecutive non-blank, non-heading, non-fence lines
        start = i
        para_lines: list[str] = []
        while (
            i < n
            and lines[i].strip() != ""
            and not (is_markdown and (_HEADING_RE.match(lines[i]) or _FENCE_RE.match(lines[i])))
        ):
            para_lines.append(lines[i])
            i += 1
        end_line = i - 1
        para_text = "\n".join(para_lines)
        locator = LineRangeLocator(start_line=start + 1, end_line=end_line + 1)
        span = SourceSpan(
            id=new_id(),
            artifact_id=artifact_id,
            span_kind=SpanKind.PARAGRAPH,
            locator_json=locator_to_json(locator),
            parent_span_id=current_parent(),
            ordinal=ordinal,
            text_content=para_text,
        )
        ordinal += 1
        result.spans.append(span)
        add_child_relation(span)

        if is_markdown:
            for link_match in _LINK_RE.finditer(para_text):
                link_span = SourceSpan(
                    id=new_id(),
                    artifact_id=artifact_id,
                    span_kind=SpanKind.LINK,
                    locator_json=locator_to_json(locator),
                    parent_span_id=span.id,
                    ordinal=ordinal,
                    text_content=link_match.group(1),
                    metadata={"url": link_match.group(2)},
                )
                ordinal += 1
                result.spans.append(link_span)

    result.parse_status = ParseStatus.PARTIAL if unclosed_fence else ParseStatus.OK
    return result


class MarkdownParser:
    kind = ArtifactKind.MARKDOWN
    parser_name = "kairos.markdown"
    parser_version = "1.0.0"

    def sniff(self, path: Path) -> bool:
        return path.suffix.lower() in MARKDOWN_EXTENSIONS

    def parse(self, path: Path, artifact_id: str) -> ParseResult:
        return _scan(path, artifact_id, is_markdown=True)


class TextParser:
    kind = ArtifactKind.TEXT
    parser_name = "kairos.text"
    parser_version = "1.0.0"

    def sniff(self, path: Path) -> bool:
        return path.suffix.lower() in TEXT_EXTENSIONS

    def parse(self, path: Path, artifact_id: str) -> ParseResult:
        return _scan(path, artifact_id, is_markdown=False)
