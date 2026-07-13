# Changelog

All notable changes to KAIROS are documented in this file.

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
