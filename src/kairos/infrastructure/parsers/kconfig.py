"""Kconfig menu JSON parser.

Input is a JSON document *describing* a Kconfig tree (menu nodes and symbols
with their prompts, types, dependencies, defaults, and choices) — not the
Kconfig DSL itself. The convention that identifies this shape is a top-level
``"kairos_kind": "kconfig_menu"`` key; see docs/architecture.md for the full
input schema.

Every node (menu or symbol) gets a span with a ``kconfig_symbol`` locator
(the menu path, e.g. ``Main/Networking/CONFIG_FOO``). Symbols additionally
become entities. Two derived relation kinds: ``menu_contains`` (parent node
-> child node, at the span level, since not every node is a symbol/entity)
and ``depends_on`` (symbol entity -> symbol entity), the latter only emitted
when the ``depends_on`` expression is a simple identifier or a ``&&``
conjunction of identifiers — a non-trivial expression (``||``, ``!``, ``=``,
parens) is kept verbatim on the span's metadata and flagged with a
diagnostic rather than guessed at.
"""

from __future__ import annotations

import json
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
from kairos.domain.json_types import JsonValue
from kairos.domain.locators import KconfigSymbolLocator, locator_to_json
from kairos.domain.models import Diagnostic, Entity, Mention, Relation, SourceSpan
from kairos.domain.parser import ParseResult

_SIMPLE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_kconfig_menu_document(document: JsonValue) -> bool:
    return isinstance(document, dict) and document.get("kairos_kind") == "kconfig_menu"


class KconfigParser:
    kind = ArtifactKind.KCONFIG
    parser_name = "kairos.kconfig"
    parser_version = "1.0.0"

    def sniff(self, path: Path) -> bool:
        if path.suffix.lower() != ".json":
            return False
        try:
            document: JsonValue = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except (json.JSONDecodeError, OSError):
            return False
        return is_kconfig_menu_document(document)

    def parse(self, path: Path, artifact_id: str) -> ParseResult:
        result = ParseResult()
        raw_text = path.read_text(encoding="utf-8", errors="replace")
        document: JsonValue = json.loads(raw_text)
        assert isinstance(document, dict)

        # symbol canonical_name -> entity_id, so depends_on can reference
        # symbols regardless of tree order (forward references are common).
        symbol_entity_ids: dict[str, str] = {}
        pending_depends: list[tuple[str, str]] = []  # (subject_entity_id, depends_on_text)

        def visit(node: dict[str, JsonValue], menu_path: str, parent_span_id: str | None) -> None:
            node_type = node.get("node_type", "menu")
            name = str(node.get("name", "?"))
            node_path = f"{menu_path}/{name}" if menu_path else name
            span_id = new_id()
            locator = KconfigSymbolLocator(menu_path=node_path)

            metadata: dict[str, object] = {
                "node_type": node_type,
                "prompt": node.get("prompt"),
                "symbol_type": node.get("type"),
                "default": node.get("default"),
                "depends_on": node.get("depends_on"),
                "choices": node.get("choices", []),
            }
            text_content = str(node.get("prompt") or name)

            result.spans.append(
                SourceSpan(
                    id=span_id,
                    artifact_id=artifact_id,
                    span_kind=(
                        SpanKind.KCONFIG_SYMBOL if node_type == "symbol" else SpanKind.KCONFIG_MENU
                    ),
                    locator_json=locator_to_json(locator),
                    parent_span_id=parent_span_id,
                    ordinal=len(result.spans),
                    text_content=text_content,
                    metadata=metadata,
                )
            )

            if parent_span_id is not None:
                result.relations.append(
                    Relation(
                        id=new_id(),
                        subject_id=parent_span_id,
                        subject_kind="span",
                        predicate=RelationPredicate.MENU_CONTAINS.value,
                        object_id=span_id,
                        object_kind="span",
                        evidence_span_id=span_id,
                        origin=Origin.DERIVED,
                        derivation_rule="kconfig.menu_containment.v1",
                        confidence=1.0,
                    )
                )

            if node_type == "symbol":
                entity_id = new_id()
                result.entities.append(
                    Entity(
                        id=entity_id,
                        canonical_name=name,
                        entity_type=EntityType.KCONFIG_SYMBOL.value,
                        origin=Origin.EXTRACTED,
                    )
                )
                result.mentions.append(
                    Mention(
                        id=new_id(),
                        entity_id=entity_id,
                        source_span_id=span_id,
                        surface_form=name,
                        extraction_rule="kconfig.symbol.v1",
                        confidence=1.0,
                    )
                )
                symbol_entity_ids[name] = entity_id
                depends_on = node.get("depends_on")
                if depends_on:
                    pending_depends.append((entity_id, str(depends_on)))

            children = node.get("children", [])
            if isinstance(children, list):
                for child in children:
                    if isinstance(child, dict):
                        visit(child, node_path, span_id)

        visit(document, "", None)

        for subject_entity_id, depends_expr in pending_depends:
            tokens = [t.strip() for t in depends_expr.split("&&")]
            if all(_SIMPLE_IDENTIFIER_RE.match(t) for t in tokens):
                for token in tokens:
                    target_entity_id = symbol_entity_ids.get(token)
                    if target_entity_id is None:
                        # Refers to a symbol outside this document; not
                        # guessed at, left as the raw text on the span only.
                        continue
                    result.relations.append(
                        Relation(
                            id=new_id(),
                            subject_id=subject_entity_id,
                            subject_kind="entity",
                            predicate=RelationPredicate.DEPENDS_ON.value,
                            object_id=target_entity_id,
                            object_kind="entity",
                            evidence_span_id=None,
                            origin=Origin.DERIVED,
                            derivation_rule="kconfig.depends_on.v1",
                            confidence=1.0,
                        )
                    )
            else:
                result.diagnostics.append(
                    Diagnostic(
                        message=(
                            f"depends_on expression not decomposed into relations "
                            f"(non-trivial): {depends_expr!r}"
                        )
                    )
                )

        result.parse_status = ParseStatus.OK
        return result
