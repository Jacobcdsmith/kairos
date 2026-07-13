"""JSON parser.

Raw bytes are already preserved verbatim by the content store — this parser
only builds the structured index: one span per JSON-path node (containers
*and* scalars), with a ``json_contains`` derived relation from each
container to its direct children so ``trace`` can walk the tree. A parse
failure never drops the file silently: it still yields one root span holding
the raw text, tagged ``parse_status=failed`` with a diagnostic.
"""

from __future__ import annotations

import json
from pathlib import Path

from kairos.domain.enums import ArtifactKind, Origin, ParseStatus, RelationPredicate, SpanKind
from kairos.domain.ids import new_id
from kairos.domain.json_types import JsonValue
from kairos.domain.locators import JsonPathLocator, locator_to_json
from kairos.domain.models import Diagnostic, Relation, SourceSpan
from kairos.domain.parser import ParseResult

_MAX_PREVIEW_CHARS = 2000


def _preview(text_value: str) -> str:
    if len(text_value) <= _MAX_PREVIEW_CHARS:
        return text_value
    return text_value[:_MAX_PREVIEW_CHARS] + "…"


class JsonParser:
    kind = ArtifactKind.JSON
    parser_name = "kairos.json"
    parser_version = "1.0.0"

    def sniff(self, path: Path) -> bool:
        return path.suffix.lower() == ".json"

    def parse(self, path: Path, artifact_id: str) -> ParseResult:
        result = ParseResult()
        raw_text = path.read_bytes().decode("utf-8", errors="replace")

        try:
            document: JsonValue = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            root_locator = JsonPathLocator(json_path="$")
            result.spans.append(
                SourceSpan(
                    id=new_id(),
                    artifact_id=artifact_id,
                    span_kind=SpanKind.JSON_CONTAINER,
                    locator_json=locator_to_json(root_locator),
                    parent_span_id=None,
                    ordinal=0,
                    text_content=_preview(raw_text),
                )
            )
            result.diagnostics.append(
                Diagnostic(message=f"Invalid JSON: {exc.msg} at line {exc.lineno}, col {exc.colno}")
            )
            result.parse_status = ParseStatus.FAILED
            return result

        ordinal_counter = [0]

        def visit(value: JsonValue, json_path: str, parent_span_id: str | None) -> str:
            span_id = new_id()
            ordinal = ordinal_counter[0]
            ordinal_counter[0] += 1
            locator = JsonPathLocator(json_path=json_path)

            if isinstance(value, dict | list):
                text_content = ""
                span_kind = SpanKind.JSON_CONTAINER
            else:
                text_content = _preview(json.dumps(value, ensure_ascii=False))
                span_kind = SpanKind.JSON_SCALAR

            result.spans.append(
                SourceSpan(
                    id=span_id,
                    artifact_id=artifact_id,
                    span_kind=span_kind,
                    locator_json=locator_to_json(locator),
                    parent_span_id=parent_span_id,
                    ordinal=ordinal,
                    text_content=text_content,
                )
            )

            if isinstance(value, dict):
                for key, child in value.items():
                    child_path = f"{json_path}.{key}"
                    child_span_id = visit(child, child_path, span_id)
                    result.relations.append(
                        Relation(
                            id=new_id(),
                            subject_id=span_id,
                            subject_kind="span",
                            predicate=RelationPredicate.JSON_CONTAINS.value,
                            object_id=child_span_id,
                            object_kind="span",
                            evidence_span_id=span_id,
                            origin=Origin.DERIVED,
                            derivation_rule="json.tree_containment.v1",
                            confidence=1.0,
                        )
                    )
            elif isinstance(value, list):
                for i, child in enumerate(value):
                    child_path = f"{json_path}[{i}]"
                    child_span_id = visit(child, child_path, span_id)
                    result.relations.append(
                        Relation(
                            id=new_id(),
                            subject_id=span_id,
                            subject_kind="span",
                            predicate=RelationPredicate.JSON_CONTAINS.value,
                            object_id=child_span_id,
                            object_kind="span",
                            evidence_span_id=span_id,
                            origin=Origin.DERIVED,
                            derivation_rule="json.tree_containment.v1",
                            confidence=1.0,
                        )
                    )

            return span_id

        visit(document, "$", None)
        result.parse_status = ParseStatus.OK
        return result
