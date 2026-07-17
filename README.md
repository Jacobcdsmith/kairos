<div align="center">

# KAIROS

**A local-first, terminal-native workspace for tracing the lineage of your own ideas.**

[![CI](https://github.com/Jacobcdsmith/kairos/actions/workflows/ci.yml/badge.svg)](https://github.com/Jacobcdsmith/kairos/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](pyproject.toml)
[![Typed: strict](https://img.shields.io/badge/pyright-strict-brightgreen)](pyproject.toml)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230)](https://github.com/astral-sh/ruff)
[![No network. No telemetry.](https://img.shields.io/badge/network-none-critical)](docs/architecture.md)

[Quick start](#quick-start) ·
[Why KAIROS](#why-kairos) ·
[CLI reference](docs/cli.md) ·
[Architecture](docs/architecture.md) ·
[Status](docs/v0.1-status.md) ·
[Contributing](CONTRIBUTING.md)

</div>

---

KAIROS helps one owner traverse a personal technical corpus, preserve the
lineage of ideas and decisions, and keep an inspectable working context
across sessions — without shipping a single byte off the machine it runs on.

It is **not** a chatbot and **not** a generic RAG wrapper. It is a
source-grounded local workspace: ingest documents, repositories, structured
configuration, logs, and notes; trace concepts and implementation artifacts
through those sources via exact, explicit relations (no embeddings, no
similarity guessing); form curated working sets called **coherence wells**;
and inspect the exact evidence — down to the line, page, JSON path, or
Kconfig symbol — behind every result KAIROS gives you.

This is the **v0.1 milestone**: the framework substrate. It is fully usable
without any LLM, requires no network access, and stores everything locally
in SQLite.

## Why KAIROS

| | |
|---|---|
| **Local-first, always** | No cloud dependency, no telemetry, no optional-but-really-mandatory network call. Every read and write stays on your machine. |
| **Corpus-native parsing** | Markdown, PDF, JSON, Kconfig-menu JSON, runtime/emulator logs, and Python repositories are each parsed by structure — headings, pages, JSON paths, symbols, sessions, AST nodes — not blindly chunked by byte count. |
| **Provenance over vibes** | Every search hit, trace node, and shown span carries its artifact id, workspace-relative path, exact locator, parser version, and provenance layer (raw / extracted / derived / user). Nothing is allowed to masquerade as source truth. |
| **Read-only toward your sources** | KAIROS ingests bytes into a content-addressed, write-once store and never reopens the original file for writing. The only writes it ever makes to *your* data are additive: notes and well membership. |
| **Cross-document traversal without embeddings** | `kairos trace` walks explicit, typed relations (`heading_contains`, `imports`, `depends_on`, `log_in_session`, ...) built from cross-artifact entity reconciliation — so a bare word in one file's paragraph can reach a sibling document through a shared heading, two hops later, deterministically. |
| **A real exit code** | Every one of the eleven commands fails loudly and non-zero with an actionable message — never a silent no-op, never a bare traceback. |

## Quick start

Requires Python 3.12+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"
```

```bash
# Create a workspace
kairos init ./my-workspace
cd my-workspace

# Ingest a file (markdown, text, PDF, JSON, Kconfig-menu JSON, logs, or
# a directory of Python files with --recursive)
kairos ingest ../notes/architecture.md

# See what's there
kairos artifacts

# Full-text search over everything ingested
kairos search "widget"

# Show one artifact's full parsed structure, with exact locators
kairos show <artifact-id>

# Trace a term or entity through direct matches and explicit relations
kairos trace "Widgets" --depth 2

# Curate a working set
kairos well create widget-work --purpose "Everything about the widget system"
kairos well add widget-work <artifact-id>
kairos well show widget-work

# Annotate anything you've ingested
kairos note add <artifact-id> "revisit this after the v0.2 redesign"

# Kconfig symbol lookup, log search with context, environment health
kairos config CONFIG_WIFI
kairos logs "connection" --level ERROR --before 2 --after 2
kairos doctor
```

Run [`scripts/demo.sh`](scripts/demo.sh) for a scripted walkthrough of every
command against the synthetic fixtures in `tests/fixtures/`.

## Release verification

Every claim on this page — offline operation, source immutability, complete
provenance, explicit relation discipline, FTS integrity — is backed by a
test that was actually run, plus a build that installs independently of
this repository checkout. See
[docs/v0.1-status.md#audit-verification](docs/v0.1-status.md#audit-verification)
for the exact commands and their actual, current results.

## The full command surface

`init` · `ingest` · `artifacts` · `show` · `search` · `trace` · `note add` /
`note list` · `well create` / `well add` / `well remove` / `well show` /
`well list` · `config` · `logs` · `doctor`

See [docs/cli.md](docs/cli.md) for the complete reference with options and
example output for every command.

## Terminal Lineage Interface (alpha)

`kairos tui` is an optional, full-screen, keyboard-first workspace over the
same v0.1 services above — three panes (Explorer, Workspace, Evidence), a
persistent `:command` line, and one visible active coherence well. It adds
no LLM, no network, no embeddings, and no new mutation beyond what the CLI
already exposes (`note add`, well activation). It's a presentation layer,
not a new substrate.

```
pip install -e ".[tui]"
kairos tui
```

See [docs/tli.md](docs/tli.md) for the full command grammar, keybindings,
provenance legend, and alpha limitations.

## How it's built

- **Storage**: SQLite as the canonical store, nine tables used verbatim
  against the spec (`artifacts`, `source_spans`, `entities`, `mentions`,
  `relations`, `notes`, `coherence_wells`, `well_members`, `events`), plus an
  FTS5 virtual table with sync triggers for full-text search — no separate
  search service, no vector database.
- **Migrations**: a single hand-written Alembic migration, run
  programmatically by `kairos init`.
- **Layering**: `domain/` (pure Python, zero framework imports) →
  `infrastructure/` (SQLAlchemy, parsers, filesystem, git) → `services/`
  (application logic) → `cli/` (Typer + Rich presentation). See
  [CONTRIBUTING.md](CONTRIBUTING.md#architecture-rules) for the enforced
  boundaries.
- **Quality gate**: Python 3.12+ strict typing end to end, Pydantic v2 at
  every process boundary, Ruff for format+lint, Pyright in strict mode, and
  a pytest suite covering every parser's well-formed *and* malformed path
  plus full CLI integration coverage.

Full detail in [docs/architecture.md](docs/architecture.md), including the
provenance model, the parser registry, and the explicit non-goals for this
milestone.

## What v0.1 doesn't do (on purpose)

Hardware/embedded systems, device clients, simulations or virtual
companions, remote node management, external messaging integrations, cloud
services, multi-agent orchestration, autonomous background execution,
self-modification, and model inference or model-provider integration are
all explicitly out of scope for this milestone — not omissions, a boundary
the project is designed around. See
[docs/architecture.md#non-goals-v01](docs/architecture.md#non-goals-v01) and
[docs/v0.1-status.md](docs/v0.1-status.md) for the full picture of what's in,
what's out, and what a later milestone might still add within this same
local-framework scope.

## Contributing

Bug reports, feature ideas, and pull requests are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md) for the development setup, architecture
rules, and the scope boundary above (read that part first, it'll save you
some work). Please also review the [Code of Conduct](CODE_OF_CONDUCT.md).
Found a security issue? See [SECURITY.md](SECURITY.md) rather than filing a
public issue.

## License

[MIT](LICENSE) © Jacob Smith
