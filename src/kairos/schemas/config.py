"""Result schema for ``kairos config``: Kconfig symbol lookup."""

from __future__ import annotations

from pydantic import BaseModel

from kairos.schemas.provenance import ProvenanceEnvelope


class ConfigSymbolResult(BaseModel):
    symbol: str
    prompt: str | None
    symbol_type: str | None
    default: str | None
    depends_on: str | None
    choices: list[str]
    children: list[str]
    provenance: ProvenanceEnvelope
