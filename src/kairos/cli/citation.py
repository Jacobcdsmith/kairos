"""Shared rendering for the provenance envelope, so every command that shows
source-derived results displays the same six required fields the same way:
artifact id, artifact kind, exact locator, parser name+version, and
provenance layer. Used by ``search``, ``trace``, ``config``, and ``logs`` so
none of them can drift out of sync with each other or quietly drop a field.
"""

from __future__ import annotations

from rich.markup import escape
from rich.table import Table

from kairos.schemas.provenance import ProvenanceEnvelope

PROVENANCE_COLUMNS = ("artifact_id", "artifact_kind", "parser", "layer")


def add_provenance_columns(table: Table, *, include_locator: bool = True) -> None:
    """Add the standard citation columns to a Rich table, in a fixed order."""
    table.add_column("artifact_id")
    table.add_column("artifact_kind")
    if include_locator:
        table.add_column("locator")
    table.add_column("parser")
    table.add_column("layer")


def provenance_cells(
    envelope: ProvenanceEnvelope, *, include_locator: bool = True
) -> tuple[str, ...]:
    """Render one envelope as escaped cell values matching ``add_provenance_columns``."""
    parser = f"{envelope.parser_name} v{envelope.parser_version}"
    if include_locator:
        return (
            envelope.artifact_id,
            escape(envelope.artifact_kind),
            escape(envelope.locator_str),
            escape(parser),
            envelope.layer,
        )
    return (
        envelope.artifact_id,
        escape(envelope.artifact_kind),
        escape(parser),
        envelope.layer,
    )


def provenance_lines(envelope: ProvenanceEnvelope) -> str:
    """Render one envelope as label:value lines, for panel-style (single-record)
    output such as ``kairos config`` — the same six fields as
    ``add_provenance_columns``/``provenance_cells``, formatted for a body of
    text instead of a table row.
    """
    parser = f"{envelope.parser_name} v{envelope.parser_version}"
    return (
        f"artifact_id: {envelope.artifact_id}\n"
        f"artifact_kind: {envelope.artifact_kind}\n"
        f"source: {envelope.source_path}\n"
        f"locator: {envelope.locator_str}\n"
        f"parser: {parser}\n"
        f"layer: {envelope.layer}"
    )
