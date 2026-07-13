"""``kairos trace <term-or-id> [--depth N] [--well <name>]``"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.markup import escape
from rich.table import Table

from kairos.cli.citation import add_provenance_columns, provenance_cells
from kairos.cli.errors import cli_command, console
from kairos.schemas.provenance import ProvenanceEnvelope
from kairos.services.context import RuntimeContext
from kairos.services.trace import trace as trace_service

_BLANK_PROVENANCE_CELLS = ("", "", "", "", "")


def _node_provenance_cells(provenance: ProvenanceEnvelope | None) -> tuple[str, ...]:
    # Entity nodes legitimately have no single owning artifact (an entity can
    # be mentioned across many documents) — blank cells, not a missing-data bug.
    if provenance is None:
        return _BLANK_PROVENANCE_CELLS
    return provenance_cells(provenance)


@cli_command
def run(
    term_or_id: Annotated[
        str, typer.Argument(help="A term, entity name, artifact id, or span id.")
    ],
    depth: Annotated[int, typer.Option("--depth", help="Maximum hops to traverse.")] = 2,
    well: Annotated[str | None, typer.Option("--well", help="Scope FTS seeding to a well.")] = None,
) -> None:
    ctx = RuntimeContext.open(Path.cwd())
    result = trace_service(ctx, term_or_id, depth=depth, well=well)

    if not result.nodes:
        console.print("[yellow]No matches.[/yellow]")
        return

    node_table = Table(title=escape(f'Trace nodes: "{term_or_id}"'))
    node_table.add_column("kind")
    node_table.add_column("id", overflow="fold")
    node_table.add_column("label", overflow="fold")
    node_table.add_column("source_path", overflow="fold")
    add_provenance_columns(node_table)
    for node in result.nodes:
        source_path = escape(node.provenance.source_path) if node.provenance else ""
        node_table.add_row(
            node.node_kind,
            node.node_id,
            escape(node.label),
            source_path,
            *_node_provenance_cells(node.provenance),
        )
    console.print(node_table)

    if result.edges:
        edge_table = Table(title="Trace edges")
        edge_table.add_column("subject")
        edge_table.add_column("predicate")
        edge_table.add_column("object")
        edge_table.add_column("layer")
        edge_table.add_column("rule")
        for edge in result.edges:
            edge_table.add_row(
                f"{edge.subject_kind}:{edge.subject_id}",
                edge.predicate,
                f"{edge.object_kind}:{edge.object_id}",
                edge.layer,
                escape(edge.derivation_rule or ""),
            )
        console.print(edge_table)
