# Changelog

All notable changes to KAIROS are documented in this file.

## [0.1.1] — 2026-07-20

Additive enhancements: agent tool adapter, demo command, streamlined install,
public-facing README overhaul with ASCII art, and TUI polish.

### Added

- **Agent tool adapter** (`src/kairos/tool.py`): importable Python module that
  wraps every KAIROS service with structured dict returns and inline source
  links (`file://#L,C` + `vscode://file/`). Functions:
  `kairos_status`, `kairos_ingest`, `kairos_search`, `kairos_trace`,
  `kairos_show`, `kairos_source_content`, `kairos_source_link`,
  `kairos_well_create/list/add/show`. Every result carries
  `artifact_id`, `source_path`, exact `locator`, and `source_link`.
- **`kairos demo` command**: self-contained cross-platform walkthrough
  (no bash required). Creates a temp workspace, runs all 8 command groups
  against test fixtures, cleans up.
- **`[all]` install extra**: single `pip install -e ".[all]"` gets you
  CLI + TUI + dev tooling.
- **`:tutorial` TUI command**: typed `:tutorial` now recognized alongside
  the existing `t` keybinding. `src/kairos/tui/commands.py` and
  `src/kairos/tui/controller.py` updated.
- **`kairos-agent-tool` Hermes skill**: persistent skill teaching the agent
  the auto-ingest → well → search → trace → source-link workflow.

### Changed

- **README restructured**: ASCII KAIROS logo banner, one-shot quick-start,
  collapsible details blocks, command reference table, demo section
  promoted, anti-goals collapsed to bottom.
- **TUI status line legend** now includes `t tutorial` (was present already).

### Fixed

- **Source link resolution** in `kairos/tool.py`: Pydantic V2 model wrapping
  no longer prevents `file://#L,C` detection — duck-typed attribute access
  now handles both domain dataclasses and Pydantic model wrappers.
- **Workspace name display** in `kairos_status`: reads from `.kairos/config.json`
  instead of a non-existent `Workspace.name` attribute.

## [0.1.0]

First release. KAIROS v0.1.0 is a local-first, terminal-native workspace for
tracing the lineage of a personal technical corpus.

### Included

- **Local-only operation**: no network access, no telemetry, no cloud
  dependency, anywhere in the codebase — verified by a socket-level
  network-block test run against the full command surface
  (`tests/integration/test_offline.py`).
- **Content-addressed raw storage**: every ingested file's bytes are hashed
  (SHA-256), stored once, and made read-only; registered source files are
  never modified, verified by a source-immutability test that fingerprints
  every fixture before and after a full command run.
- **SQLite + FTS5 local search**: a canonical SQLite store (nine tables) plus
  a trigger-synced FTS5 index, with `kairos doctor` checks for both raw-byte
  integrity and search-index referential consistency.
- **Exact provenance and citations**: every search hit, trace node/edge,
  `show` span, `config` lookup, and `logs` hit carries its artifact id,
  workspace-relative path, artifact kind, an exact locator, parser
  name+version, and its raw/extracted/derived/user layer — rendered through
  one shared citation component (`kairos.cli.citation`) so no command can
  drop a field.
- **Explicit, deterministic relation traversal**: `kairos trace` walks only
  typed, evidence-backed relations (see `docs/relation-registry.md`) —
  no embeddings, no similarity search, no vector index.
- **Notes and coherence wells**: owner-authored annotations and curated
  working sets, stored separately from extracted/derived data.
- **Six corpus-native parsers**: plain text, Markdown, PDF, JSON,
  Kconfig-menu JSON, runtime/emulator logs, and Python repository files
  (AST-based) — each with well-formed and malformed-input test coverage,
  and a "never silently discard" guarantee backed by diagnostics.
- **Offline enforcement and integrity checks**: `kairos doctor` reports
  FTS5 availability, workspace/schema health, content-store reachability,
  stored-blob hash integrity (`content_integrity`), and search-index
  consistency (`fts_consistency`).
- **A documented CLI exit-code contract**: `0` success, `1` expected
  user/input/domain failure, `2` workspace/configuration/integrity failure,
  `3` unexpected internal error (traceback suppressed unless
  `KAIROS_DEBUG=1`) — see `docs/cli.md`.
- **An enforced architecture boundary**: the domain layer has zero
  dependency on Typer, Rich, SQLAlchemy, Alembic, or pypdf, checked by a
  CI-run test, not just convention.

### Intentionally not included

No LLM or model-provider integration; no embeddings or vector/similarity
search; no cloud services, telemetry, analytics, or API keys; no autonomous
execution, background jobs, multi-agent orchestration, or self-modification;
no source-file mutation or shell execution beyond read-only `git` metadata
reads; no hardware, device, or remote-client functionality; no TUI or web
interface. These are boundaries the project is designed around, not gaps —
see `docs/architecture.md#non-goals-v01`.
