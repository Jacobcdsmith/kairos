"""The shared provenance envelope. Every search hit, trace node, and show
result is wrapped in this — the mechanism enforcing that nothing masquerades
as source truth without saying which of raw/extracted/derived/user it is.
"""

from __future__ import annotations

from dataclasses import fields
from typing import Annotated, Literal

from pydantic import BaseModel, Field

from kairos.domain import locators as domain_locators

Layer = Literal["raw", "extracted", "derived", "user"]


class PdfPageLocatorModel(BaseModel):
    locator_kind: Literal["pdf_page"] = "pdf_page"
    page: int


class LineRangeLocatorModel(BaseModel):
    locator_kind: Literal["line_range"] = "line_range"
    start_line: int
    end_line: int


class JsonPathLocatorModel(BaseModel):
    locator_kind: Literal["json_path"] = "json_path"
    json_path: str


class KconfigSymbolLocatorModel(BaseModel):
    locator_kind: Literal["kconfig_symbol"] = "kconfig_symbol"
    menu_path: str


class RepoFileLinesLocatorModel(BaseModel):
    locator_kind: Literal["repo_file_lines"] = "repo_file_lines"
    file_path: str
    start_line: int
    end_line: int


class LogEventLocatorModel(BaseModel):
    locator_kind: Literal["log_event"] = "log_event"
    line_number: int
    timestamp: str | None = None


LocatorModel = Annotated[
    PdfPageLocatorModel
    | LineRangeLocatorModel
    | JsonPathLocatorModel
    | KconfigSymbolLocatorModel
    | RepoFileLinesLocatorModel
    | LogEventLocatorModel,
    Field(discriminator="locator_kind"),
]

_MODEL_BY_DOMAIN_KIND: dict[type, type[BaseModel]] = {
    domain_locators.PdfPageLocator: PdfPageLocatorModel,
    domain_locators.LineRangeLocator: LineRangeLocatorModel,
    domain_locators.JsonPathLocator: JsonPathLocatorModel,
    domain_locators.KconfigSymbolLocator: KconfigSymbolLocatorModel,
    domain_locators.RepoFileLinesLocator: RepoFileLinesLocatorModel,
    domain_locators.LogEventLocator: LogEventLocatorModel,
}


def locator_model_from_domain(locator: domain_locators.Locator) -> BaseModel:
    model_cls = _MODEL_BY_DOMAIN_KIND[type(locator)]
    data = {f.name: getattr(locator, f.name) for f in fields(locator) if f.name != "kind"}
    return model_cls(**data)


class ProvenanceEnvelope(BaseModel):
    """artifact ID, workspace-relative source path, artifact kind, exact
    locator, extraction/parser version, and raw|extracted|derived|user.
    """

    artifact_id: str
    source_path: str
    artifact_kind: str
    locator: LocatorModel
    locator_str: str
    parser_name: str
    parser_version: str
    layer: Layer


def build_envelope(
    *,
    artifact_id: str,
    source_path: str,
    artifact_kind: str,
    locator: domain_locators.Locator,
    parser_name: str,
    parser_version: str,
    layer: Layer,
) -> ProvenanceEnvelope:
    return ProvenanceEnvelope(
        artifact_id=artifact_id,
        source_path=source_path,
        artifact_kind=artifact_kind,
        locator=locator_model_from_domain(locator),  # type: ignore[arg-type]
        locator_str=locator.to_str(),
        parser_name=parser_name,
        parser_version=parser_version,
        layer=layer,
    )
