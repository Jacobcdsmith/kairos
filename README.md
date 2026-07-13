# KAIROS

KAIROS is a local-first, terminal-native workspace for a single persistent
agent runtime. It helps one owner traverse a personal technical corpus,
preserve the lineage of ideas and decisions, and maintain inspectable
working context across sessions.

It is not a chatbot and not a generic RAG wrapper. It is a source-grounded
local workspace: ingest documents, repositories, structured configuration,
logs, and notes; trace concepts and implementation artifacts through those
sources; form curated working sets called **coherence wells**; and inspect
the exact evidence behind every retrieval or relation.

This is the v0.1 milestone: the framework substrate. It is fully usable
without any LLM, requires no network access, and stores everything locally
in SQLite. See [docs/v0.1-status.md](docs/v0.1-status.md) for what's in and
out of scope, and [docs/architecture.md](docs/architecture.md) for how it's
built.

## Installation

Requires Python 3.12+.

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -e ".[dev]"
```

## Quick start

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

Run `scripts/demo.sh` for a scripted walkthrough of every command against
synthetic fixtures.

## Every command's full reference

See [docs/cli.md](docs/cli.md) for the complete command list, options, and
example output.

## Development

```bash
ruff format src tests
ruff check src tests
pyright
pytest
```
