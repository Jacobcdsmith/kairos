"""Kconfig menu JSON parser: symbols, entities, menu_contains, depends_on."""

from __future__ import annotations

import json
from pathlib import Path
from typing import cast

from kairos.domain.enums import EntityType, ParseStatus, SpanKind
from kairos.domain.locators import KconfigSymbolLocator, locator_from_json
from kairos.infrastructure.parsers.kconfig import KconfigParser, is_kconfig_menu_document
from kairos.infrastructure.parsers.registry import ParserRegistry

FIXTURES = Path(__file__).parent.parent / "fixtures" / "kconfig"


def test_sniff_recognizes_kconfig_menu_shape() -> None:
    assert KconfigParser().sniff(FIXTURES / "sample_menu.json") is True


def test_registry_prefers_kconfig_over_generic_json() -> None:
    registry = ParserRegistry()
    parser = registry.resolve(FIXTURES / "sample_menu.json")
    assert isinstance(parser, KconfigParser)


def test_is_kconfig_menu_document_rejects_plain_json() -> None:
    assert is_kconfig_menu_document({"just": "json"}) is False


def test_symbols_become_entities_with_mentions() -> None:
    parser = KconfigParser()
    result = parser.parse(FIXTURES / "sample_menu.json", "artifact-kconfig")

    assert result.parse_status == ParseStatus.OK
    symbol_entities = [
        e for e in result.entities if e.entity_type == EntityType.KCONFIG_SYMBOL.value
    ]
    assert {e.canonical_name for e in symbol_entities} == {
        "CONFIG_WIFI",
        "CONFIG_WIFI_POWER_SAVE",
    }
    # every symbol entity must be grounded by a mention to its own span
    assert len(result.mentions) == len(symbol_entities)


def test_menu_contains_and_depends_on_relations() -> None:
    parser = KconfigParser()
    result = parser.parse(FIXTURES / "sample_menu.json", "artifact-kconfig")

    menu_relations = [r for r in result.relations if r.predicate == "menu_contains"]
    assert len(menu_relations) == 3  # Main->Networking, Networking->WIFI, Networking->POWER_SAVE

    depends = [r for r in result.relations if r.predicate == "depends_on"]
    assert len(depends) == 1
    assert depends[0].subject_kind == "entity"
    assert depends[0].object_kind == "entity"


def test_symbol_span_has_kconfig_locator() -> None:
    parser = KconfigParser()
    result = parser.parse(FIXTURES / "sample_menu.json", "artifact-kconfig")

    symbol_span = next(s for s in result.spans if s.span_kind == SpanKind.KCONFIG_SYMBOL)
    locator = locator_from_json(symbol_span.locator_json)
    assert isinstance(locator, KconfigSymbolLocator)
    assert locator.menu_path.startswith("Main/Networking/")


def test_unknown_fields_preserved_in_extra_metadata(tmp_path: Path) -> None:
    """A field this parser doesn't know about (e.g. a project-specific
    ``help`` string) must still be visible via ``kairos show``/``kairos
    config`` — not silently dropped just because it isn't one of the six
    fields this parser explicitly interprets.
    """
    doc: dict[str, object] = {
        "kairos_kind": "kconfig_menu",
        "name": "Main",
        "children": [
            {
                "node_type": "symbol",
                "name": "CONFIG_FOO",
                "prompt": "Foo",
                "type": "bool",
                "help": "A longer explanation not modeled by any known field.",
                "range": [0, 100],
                "children": [],
            }
        ],
    }
    path = tmp_path / "extra.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    result = KconfigParser().parse(path, "artifact-extra")
    symbol_span = next(s for s in result.spans if s.span_kind == SpanKind.KCONFIG_SYMBOL)
    extra = cast("dict[str, object]", symbol_span.metadata["extra"])
    assert extra["help"] == "A longer explanation not modeled by any known field."
    assert extra["range"] == [0, 100]
    assert result.parse_status == ParseStatus.OK


def test_non_dict_child_is_diagnosed_not_dropped(tmp_path: Path) -> None:
    doc: dict[str, object] = {
        "kairos_kind": "kconfig_menu",
        "name": "Main",
        "children": [
            {"node_type": "symbol", "name": "CONFIG_A", "children": []},
            "not-a-node",
        ],
    }
    path = tmp_path / "malformed_child.json"
    path.write_text(json.dumps(doc), encoding="utf-8")

    result = KconfigParser().parse(path, "artifact-malformed")
    assert result.parse_status == ParseStatus.PARTIAL
    assert any("not-a-node" in d.message for d in result.diagnostics)
    # the well-formed sibling is still parsed, not dropped along with its bad sibling
    assert any(e.canonical_name == "CONFIG_A" for e in result.entities)
