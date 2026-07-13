"""``kairos config <symbol>`` — look up one Kconfig symbol by name."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from kairos.domain.enums import EntityType
from kairos.domain.errors import ConfigSymbolNotFoundError
from kairos.domain.locators import locator_from_json
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.repositories import (
    find_entities_by_name,
    get_artifact,
    get_span,
    list_mentions_for_entity,
    list_relations_from,
)
from kairos.schemas.config import ConfigSymbolResult
from kairos.schemas.provenance import build_envelope
from kairos.services.context import RuntimeContext


def _opt_str(value: object) -> str | None:
    return None if value is None else str(value)


def _str_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(v) for v in cast("list[object]", value)]


def get_config_symbol(ctx: RuntimeContext, symbol: str) -> ConfigSymbolResult:
    with session_scope(ctx.session_factory) as session:
        entities = [
            e
            for e in find_entities_by_name(session, symbol)
            if e.entity_type == EntityType.KCONFIG_SYMBOL.value
        ]
        if not entities:
            raise ConfigSymbolNotFoundError(f"No Kconfig symbol named: {symbol}")
        entity = entities[0]

        mentions = list_mentions_for_entity(session, entity.id)
        if not mentions:
            raise ConfigSymbolNotFoundError(f"Symbol {symbol!r} has no grounding span")
        span_row = get_span(session, mentions[0].source_span_id)
        if span_row is None:
            raise ConfigSymbolNotFoundError(f"Symbol {symbol!r} has no grounding span")

        artifact_row = get_artifact(session, span_row.artifact_id)
        if artifact_row is None:
            raise ConfigSymbolNotFoundError(f"Symbol {symbol!r} has no grounding artifact")

        children: list[str] = []
        for rel in list_relations_from(session, span_row.id):
            if rel.predicate == "menu_contains":
                child_span = get_span(session, rel.object_id)
                if child_span is not None:
                    children.append(child_span.text_content)

        metadata = span_row.metadata_json
        envelope = build_envelope(
            artifact_id=artifact_row.id,
            source_path=ctx.workspace.relative_path(Path(artifact_row.original_path)),
            artifact_kind=artifact_row.kind,
            locator=locator_from_json(span_row.locator_json),
            parser_name=artifact_row.parser_name,
            parser_version=artifact_row.parser_version,
            layer="extracted",
        )

        return ConfigSymbolResult(
            symbol=symbol,
            prompt=_opt_str(metadata.get("prompt")),
            symbol_type=_opt_str(metadata.get("symbol_type")),
            default=_opt_str(metadata.get("default")),
            depends_on=_opt_str(metadata.get("depends_on")),
            choices=_str_list(metadata.get("choices")),
            children=children,
            provenance=envelope,
        )
