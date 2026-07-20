"""``kairos demo`` — a self-contained, cross-platform walkthrough.

Creates a temporary workspace, every command through its paces, prints
formatted results, and cleans up on exit. No bash, no external scripts,
no network. Safe to re-run: each invocation starts fresh.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import typer
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from kairos.cli.errors import cli_command
from kairos.services.context import RuntimeContext
from kairos.services.ingest import ingest
from kairos.services.search import search
from kairos.services.trace import trace
from kairos.services.show import show
from kairos.services.wells import create_well, add_member, show_well
from kairos.services.doctor import run_doctor

demo_console = Console()

_LOGO = """\
[bold cyan]
             ╭──────────────────────────╮
             │   K A I R O S   v 0 . 1   │
             │  local • source-grounded  │
             ╰──────────────────────────╯
[/bold cyan]"""


def _heading(text: str) -> None:
    demo_console.print()
    demo_console.print(Panel(f"[bold yellow]{text}[/bold yellow]", width=72))


def _ok(text: str) -> None:
    demo_console.print(f"  [green]✓[/green] {text}")


def _info(text: str) -> None:
    demo_console.print(f"    [dim]{text}[/dim]")


def _find_fixtures() -> Path:
    """Locate the test fixtures shipped with the package."""
    here = Path(__file__).resolve()
    # Walk up to find tests/fixtures/ relative to project root
    for ancestor in here.parents:
        candidate = ancestor / "tests" / "fixtures"
        if candidate.is_dir():
            return candidate
    msg = "tests/fixtures/ not found. Ensure the kairos package is installed in editable mode."
    demo_console.print(f"[red]Error:[/red] {msg}")
    raise typer.Exit(code=1)


@cli_command
def run() -> None:
    """Run a scripted walkthrough of every KAIROS v0.1 command."""

    fixtures = _find_fixtures()
    tmp_root = Path(tempfile.mkdtemp(prefix="kairos-demo-"))
    workspace_path = tmp_root / "demo-workspace"

    demo_console.print(_LOGO)
    demo_console.print(
        Panel(
            "[dim]A temporary workspace will be created and destroyed.\n"
            "Every result shown is real — sourced from the test fixtures shipped with KAIROS.[/dim]",
            width=72,
        )
    )

    try:
        # -- init -----------------------------------------------------------
        _heading("1.  init — create a workspace")
        from kairos.infrastructure.filesystem.workspace import init_workspace
        from kairos.infrastructure.database.migrate import upgrade_to_head

        workspace = init_workspace(workspace_path, name="demo-workspace")
        upgrade_to_head(workspace.db_path)
        ctx = RuntimeContext.open(workspace_path)
        _ok(f"Workspace created at {workspace_path}")
        _info(f"Database: {workspace.db_path.name}")

        # -- ingest ----------------------------------------------------------
        _heading("2.  ingest — parse documents by their actual structure")

        md_file = fixtures / "text" / "sample.md"
        ingest(ctx, md_file)
        _ok(f"Markdown: {md_file.name} (headings → entities, spans → relations)")

        json_file = fixtures / "json" / "sample.json"
        ingest(ctx, json_file)
        _ok(f"JSON: {json_file.name} (every value at its JSON path)")

        kconfig_file = fixtures / "kconfig" / "sample_menu.json"
        ingest(ctx, kconfig_file)
        _ok(f"Kconfig: {kconfig_file.name} (symbols, menus, dependencies)")

        log_file = fixtures / "logs" / "sample.log"
        ingest(ctx, log_file)
        _ok(f"Logs: {log_file.name} (sessions, levels, timestamps)")

        python_dir = fixtures / "repo"
        ingest(ctx, python_dir, recursive=True)
        _ok(f"Python repo: {python_dir.name}/ (AST nodes → imports → classes)")

        _info(f"All files parsed by structure, not chunked by byte count.")

        # -- artifacts -------------------------------------------------------
        _heading("3.  artifacts — what's in the workspace")
        from kairos.services.artifacts import list_artifacts

        all_artifacts = list_artifacts(ctx)
        table = Table("kind", "source_path", "parser", "status")
        for a in all_artifacts:
            status = "[green]ok[/green]" if a.parse_status == "ok" else f"[yellow]{a.parse_status}[/yellow]"
            table.add_row(a.kind, escape(a.source_path), a.parser_name, status)
        demo_console.print(table)
        _info(f"{len(all_artifacts)} artifacts ingested.")

        # -- search ----------------------------------------------------------
        _heading("4.  search — full-text with provenance, no embeddings")
        search_result = search(ctx, "widget", limit=5)
        if search_result.hits:
            st = Table("path", "locator", "layer", "snippet")
            for h in search_result.hits[:3]:
                st.add_row(
                    escape(h.provenance.source_path),
                    h.provenance.locator_str,
                    h.provenance.layer,
                    escape(h.snippet[:80]),
                )
            demo_console.print(st)
            _ok(f"{search_result.hits[0].provenance.locator_str} — exact locator, extracted by parser")
        else:
            _info("(no hits for 'widget' — fixtures may vary)")

        # -- show ------------------------------------------------------------
        _heading("5.  show — inspect an artifact's full parsed structure")
        md_artifact = next((a for a in all_artifacts if a.kind == "markdown"), None)
        if md_artifact:
            detail = show(ctx, md_artifact.id)
            st = Table("span", "kind", "locator")
            for s in detail.spans[:6]:
                st.add_row(
                    escape(s.text_content[:50]),
                    s.span_kind,
                    s.provenance.locator_str,
                )
            demo_console.print(st)
            _ok(f"{len(detail.spans)} spans across {md_artifact.kind} artifact")

        # -- trace -----------------------------------------------------------
        _heading("6.  trace — follow explicit relations across documents")
        trace_result = trace(ctx, "gadgets", depth=3)
        if trace_result.nodes:
            _ok(f"{len(trace_result.nodes)} nodes, {len(trace_result.edges)} edges")
            for n in trace_result.nodes[:4]:
                layer = n.provenance.layer if n.provenance else "?"
                _info(f"  [{n.node_kind}] {n.label}  ({layer})")
        else:
            _info("(trace 'gadgets' returned no nodes with these fixtures)")

        # -- well ------------------------------------------------------------
        _heading("7.  well — curate a coherence working set")
        w = create_well(ctx, "widget-system", "Widget-related artifacts")
        _ok(f"Well 'widget-system' created ({w.id[:8]}…)")
        if md_artifact:
            add_member(ctx, "widget-system", md_artifact.id, note="primary spec")
            _ok(f"Added {md_artifact.kind} artifact to well")
        well_detail = show_well(ctx, "widget-system")
        _info(f"{well_detail.well.member_count} member(s) in well")

        # -- doctor ----------------------------------------------------------
        _heading("8.  doctor — workspace health checks")
        report = run_doctor(ctx)
        for c in report.checks[:5]:
            status = "[green]ok[/green]" if c.ok else "[red]FAIL[/red]"
            demo_console.print(f"  {status}  {c.name}")
        _info(f"Healthy: {report.healthy}")

        # -- done ------------------------------------------------------------
        _heading("✓  Demo complete")
        demo_console.print(
            Panel(
                "Every KAIROS v0.1 command ran successfully against the test fixtures.\n"
                "All parsing is structure-aware (AST, headings, JSON paths, Kconfig symbols,\n"
                "log sessions). All results carry provenance: artifact id, exact locator,\n"
                "parser name, parser version, provenance layer.\n\n"
                "[dim]Temporary workspace has been removed. Nothing was written to your sources.[/dim]",
                width=72,
            )
        )

    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)
