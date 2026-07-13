# KAIROS v0.1 — Implementation Plan

This document is written before any code exists. It fixes the assumptions,
repository layout, schema, migration strategy, parser design, test plan, and
commit sequence that the rest of the milestone follows.

> **Historical note (post-implementation-audit):** this is a point-in-time
> planning document, not the live contract — see
> [docs/architecture.md](architecture.md), [docs/cli.md](cli.md), and
> [docs/v0.1-status.md](v0.1-status.md) for what actually shipped. One
> concrete drift: §5 below describes diagnostics being recorded "into an
> `events` row (`event_type="ingest.diagnostic"`)" — this was never
> implemented; diagnostics are recorded in the artifact's `metadata_json`
> only (still fully non-silent, just not as a separate event type). See
> [docs/v0.1-audit.md](v0.1-audit.md) for the full reconciliation.

## 1. Assumptions

- Target platform for development/testing: Windows 11 with Python 3.12+,
  invoked via a POSIX-ish shell (Git Bash) or PowerShell. The framework itself
  is not Windows-specific; paths are handled with `pathlib`.
- "Workspace" means a directory containing a `.kairos/` control directory,
  created by `kairos init`. All KAIROS state lives under `.kairos/`:
  - `.kairos/kairos.db` — SQLite database (schema below).
  - `.kairos/content/` — content-addressed raw source storage, one file per
    ingested artifact, named by its sha256 hash.
  - `.kairos/events.jsonl` — append-only mirror of the `events` table, one
    JSON object per line, for reproducible ingest records and offline
    inspection without SQLite.
  - `.kairos/config.json` — workspace-level configuration (name, created_at).
- A single owner runs a single instance of the CLI against a single workspace
  at a time. No concurrent-writer story is required for v0.1; SQLite's
  default locking is sufficient.
- "Repository files" ingestion (parser 6) means ingesting a directory tree as
  a set of individual artifacts (one per file), reusing the text/JSON/Python
  parsers per-file, plus Git metadata (branch, commit, remote) recorded once
  per ingest run when the ingested path is inside a Git working tree. KAIROS
  never invokes `git` in a way that mutates the target repository — metadata
  reads only (`git rev-parse`, `git log -1`, `git remote -v`), and failures
  to read Git metadata are non-fatal (recorded as `null` metadata).
- Embeddings, network calls, and model inference are out of scope, so
  "search" means SQLite FTS5 full-text search plus structured filters
  (kind, well membership), and "trace" means graph traversal over explicit
  `relations` rows plus FTS matches — no vector similarity.
- No LLM is required to run any command in this milestone. There is no LLM
  integration point in v0.1 at all (out of scope per the milestone brief);
  the `origin` vocabulary reserves a `model` value for a future milestone but
  nothing in v0.1 produces it.

## 2. Repository tree

```
kairos/
  pyproject.toml
  README.md
  .gitignore
  docs/
    implementation-plan.md
    architecture.md
    cli.md
    v0.1-status.md
  scripts/
    demo.sh
  src/kairos/
    __init__.py
    domain/
      __init__.py
      enums.py            # ArtifactKind, SpanKind, Origin, ParseStatus, EntityType, RelationPredicate
      models.py            # frozen dataclasses mirroring the schema (Artifact, SourceSpan, Entity, Mention, Relation, Note, CoherenceWell, WellMember, Event)
      locators.py          # locator value objects + serialize/parse to string form
      parser.py            # Parser Protocol, ParseResult, Diagnostic
      errors.py             # KairosError and subclasses
    infrastructure/
      database/
        __init__.py
        engine.py            # engine/session factory, sqlite pragmas, FTS5 capability check
        orm.py               # SQLAlchemy 2.x Mapped/mapped_column models
        repositories.py       # thin CRUD + query helpers over the ORM
        fts.py                 # FTS5 query helpers (raw text())
        migrations/
          env.py
          script.py.mako
          versions/
            0001_initial_schema.py
      filesystem/
        __init__.py
        workspace.py          # Workspace: locate/create .kairos/, config.json
        content_store.py       # content-hash addressed raw storage
      git/
        __init__.py
        metadata.py           # read-only git metadata extraction
      parsers/
        __init__.py
        registry.py            # kind -> parser lookup, extension/content sniffing
        text_markdown.py
        pdf.py
        json_parser.py
        kconfig.py
        logs.py
        repository_files.py     # walks a directory, dispatches per-file, Python AST parsing
    schemas/
      __init__.py
      provenance.py           # ProvenanceEnvelope, Locator discriminated union
      artifact.py
      span.py
      search.py
      trace.py
      note.py
      well.py
      config.py
      logs.py
      common.py               # CommandResult envelope, error schema
    services/
      __init__.py
      events.py                # append_event: DB row + JSONL mirror
      ingest.py
      artifacts.py
      show.py
      search.py
      trace.py
      notes.py
      wells.py
      config_query.py
      logs_query.py
      doctor.py
    cli/
      __init__.py
      main.py                  # Typer app assembly, Rich console, exit-code handling
      commands/
        init.py
        ingest.py
        artifacts.py
        show.py
        search.py
        trace.py
        note.py
        well.py
        config.py
        logs.py
        doctor.py
  tests/
    fixtures/
      text/sample.md
      pdf/sample.pdf              # generated by a fixture-build helper, checked in
      json/sample.json
      kconfig/sample_menu.json
      logs/sample.log
      repo/                       # small synthetic repo with .py files + .git
    unit/
      test_parsers_text.py
      test_parsers_pdf.py
      test_parsers_json.py
      test_parsers_kconfig.py
      test_parsers_logs.py
      test_parsers_repository.py
      test_locators.py
      test_content_store.py
    integration/
      test_cli_ingest_search_show.py
      test_cli_trace.py
      test_cli_note_well.py
      test_cli_config_logs.py
      test_cli_doctor.py
      conftest.py
```

## 3. Schema — confirmed, with additions

The nine tables (`artifacts`, `source_spans`, `entities`, `mentions`,
`relations`, `notes`, `coherence_wells`, `well_members`, `events`) are used
**verbatim** as specified — column names and table names are not renamed or
restructured. SQLAlchemy ORM models map 1:1 onto them.

Additions (not deviations — the base schema is silent on full-text search
and the spec calls for FTS5 explicitly):

- `source_spans_fts` — an FTS5 virtual table indexing `text_content`, with
  `span_id UNINDEXED` for the join key back to `source_spans.id`, plus
  `artifact_id UNINDEXED` and `span_kind UNINDEXED` for cheap pre-filtering.
  Populated and kept in sync by three SQL triggers (`AFTER INSERT`,
  `AFTER UPDATE`, `AFTER DELETE` on `source_spans`) created in the same
  migration, so no code path can write a span without the index following.
- Indexes: `artifacts(sha256)` unique, `artifacts(kind)`, `source_spans(artifact_id)`,
  `source_spans(parent_span_id)`, `mentions(entity_id)`, `mentions(source_span_id)`,
  `relations(subject_id)`, `relations(object_id)`, `well_members(well_id)`,
  `notes(target_id)`.

### `origin` vocabulary (entities, relations) and the provenance envelope

Every row that can carry an `origin` uses exactly these values:
`raw`, `extracted`, `derived`, `user`, and `model` (reserved, unused in v0.1
— nothing in this milestone writes `model`). This is the mechanism behind
"nothing may masquerade as source truth":

- `raw` — the artifact bytes themselves (not entities/relations; artifacts
  have no `origin` column, they *are* the raw layer).
- `extracted` — deterministic parser output: source spans always, and any
  entity/mention/relation a parser emits directly (confidence 1.0, tagged
  with `parser_name`/`parser_version` via the owning artifact).
  are populated for extracted entities.
- `derived` — a relation or entity produced by a rule operating over already-
  extracted data (e.g. "heading H2 under H1" or "import X resolves to module
  Y"). Always carries a human-readable `derivation_rule` string.
- `user` — notes, and well membership, and any entity/relation a future
  command lets the owner assert directly (v0.1 only writes `user` on
  `notes` and `well_members`, which don't have an `origin` column
  themselves but are structurally the user-authored layer by table choice).

Every CLI-facing result (search hit, trace node/edge, `show` output) is
wrapped in a single shared `ProvenanceEnvelope` (schemas/provenance.py):

```
artifact_id, source_path (workspace-relative), artifact_kind,
locator (discriminated union, see below), locator_str (serialized form
accepted back by `kairos show --locator`), parser_name, parser_version,
layer: Literal["raw", "extracted", "derived", "user"]
```

`Locator` is a discriminated union on `locator_kind`: `pdf_page`,
`line_range`, `json_path`, `kconfig_symbol`, `repo_file_lines`, `log_event`.
Each variant serializes to and parses from a compact string form (e.g.
`page:12`, `lines:10-14`, `json:$.a.b[2]`, `kconfig:MENU/SYMBOL`,
`repo:src/foo.py:10-14`, `log:1723:2024-01-01T00:00:03Z`) so it round-trips
through the CLI.

## 4. Migration strategy

Alembic is used for its migration *mechanism* (versioned upgrade scripts,
`alembic_version` tracking) but not for autogenerate — autogenerate cannot
see virtual tables or triggers, and hand-written DDL is more auditable for a
provenance-sensitive schema. v0.1 ships exactly **one** migration,
`0001_initial_schema.py`, containing:

1. `CREATE TABLE` for all nine schema tables (via `op.create_table`, matching
   the ORM `orm.py` definitions).
2. Standard indexes (via `op.create_index`).
3. Raw DDL (`op.execute`) for `source_spans_fts` (FTS5) and the three sync
   triggers.

`kairos init` runs `alembic upgrade head` programmatically (via Alembic's
`Config`/`command.upgrade`, not a subprocess) against the new workspace's
`kairos.db`. Later milestones add further versioned migrations; v0.1 does
not need a second one.

## 5. Parser design

Shared interface (`domain/parser.py`):

```python
class Parser(Protocol):
    kind: ArtifactKind
    parser_name: str
    parser_version: str
    def sniff(self, path: Path) -> bool: ...
    def parse(self, path: Path, artifact_id: str) -> ParseResult: ...
```

`ParseResult` bundles: `spans: list[SourceSpan]`, `entities: list[Entity]`,
`mentions: list[Mention]`, `relations: list[Relation]`,
`diagnostics: list[Diagnostic]`, `parse_status: ParseStatus` (`ok`,
`partial`, `failed`). A parser **never raises** to signal malformed input; it
downgrades to `partial`/`failed`, records a `Diagnostic` (message + optional
locator), and returns whatever spans it *could* recover. `ingest` persists
diagnostics into the artifact's `metadata_json` and into an `events` row
(`event_type="ingest.diagnostic"`), so nothing is silently dropped.

Each parser must emit at least one `derived` relation type so `trace` has
edges, not just nodes:

1. **Text/Markdown** — spans: headings, paragraphs, fenced code blocks,
   links, each with a `line_range` locator and `ordinal` for document order;
   heading spans get `parent_span_id` set to the nearest enclosing heading
   (document tree via `parent_span_id`, independent of the relations table).
   Derived relation: `heading_contains` (heading entity -> child paragraph/
   code-block span) recorded as a `relations` row with `derivation_rule =
   "markdown.heading_containment.v1"`.
2. **PDF** — one span per page (`pdf_page` locator) holding extracted text;
   pages with no extractable text still get a span with empty
   `text_content` and a `Diagnostic("no_extractable_text", page=n)`, per the
   "never silently discard" rule. Derived relation: `page_precedes` linking
   consecutive page spans, enabling multi-hop trace across a document.
3. **JSON** — raw bytes preserved untouched in the content store; one span
   per scalar leaf at `json_path` locator granularity, plus spans for object/
   array container nodes (empty `text_content`, used as parents). Derived
   relation: `json_contains` (parent path -> child path), built from the
   natural tree, `derivation_rule = "json.tree_containment.v1"`.
4. **Kconfig menu JSON** — input is a JSON document describing a Kconfig
   tree (menu nodes, symbols, prompts, types, dependencies, defaults,
   choices — this is JSON-shaped Kconfig metadata, not raw `Kconfig` DSL
   parsing). One span per menu/symbol node with a `kconfig_symbol` locator
   (`Menu/Path/SYMBOL`). Each symbol becomes an `entity` (`entity_type =
   "kconfig_symbol"`, `origin = "extracted"`). Derived relations:
   `menu_contains` (parent menu -> child symbol/menu) and `depends_on`
   (symbol -> symbol, parsed from the `depends on` field when it's a simple
   identifier or `A && B` conjunction — non-trivial expressions are recorded
   as a span attribute, not silently guessed at).
5. **Runtime/emulator logs** — line-oriented parser recognizing a
   timestamp, level, component/tag, and message via a configurable regex
   (default pattern documented in architecture.md); one span per log line
   (`log_event` locator = line number + timestamp), lines that don't match
   the pattern still get a span (`level=None`) plus a `Diagnostic`. Session/
   boot boundaries are detected via a configurable marker line and recorded
   as `entities` (`entity_type = "log_session"`); derived relation
   `log_in_session` (session entity -> each log line span's evidence).
6. **Repository files** — walks a directory (respecting `--recursive`),
   dispatches each file to the text/JSON/repository-file-specific handling
   by extension; `.py` files get a dedicated Python AST pass producing spans
   for modules, classes, functions (line-range locators) and `entities` for
   each (module/class/function). Derived relation: `imports` (module entity
   -> imported module entity, resolved only when the import target is
   another ingested file in the same run; unresolved imports are recorded
   as a span attribute, not guessed). Git metadata (branch, HEAD commit,
   remote URL if any) is attached to the top-level artifact's
   `metadata_json` when the ingested path is inside a Git working tree.

`registry.py` picks a parser by extension first, falling back to content
sniffing (e.g. `{` prefix for JSON, `%PDF-` magic bytes for PDF) so
extension-less files still ingest.

## 6. Test plan

- **Unit** — one test module per parser against a small synthetic fixture,
  asserting: span count/kinds/locators, at least one derived relation,
  `parse_status`, and diagnostics on a deliberately malformed variant of
  each fixture (e.g. a JSON file with a trailing comma handled as `failed`
  with a diagnostic, not a crash; a PDF-shaped-but-empty page). Also unit
  tests for locator string round-tripping and the content store's hash
  addressing / never-overwrite guarantee.
- **Integration** — drive the actual Typer CLI (via `CliRunner`) against a
  temp workspace: init -> ingest each fixture kind -> artifacts/show/search
  return expected provenance-tagged results -> a **>=2-hop trace** test
  (e.g. markdown heading -> paragraph -> a term inside that paragraph that
  also appears in a second artifact) proving traversal actually crosses
  relations, not just FTS matches -> note add/list -> well create/add/
  remove/show/list -> config query against the Kconfig fixture -> logs
  query with `--before/--after/--level` -> doctor reports healthy on a good
  workspace and reports the FTS5-capability check explicitly.
- Every command's non-zero exit code on failure is asserted at least once
  (bad artifact id, ingesting a nonexistent path, duplicate well name).

## 7. Staged commit plan

All git operations run with `kairos/` as the working directory (this repo is
nested inside the user's home-directory git repo; it is never touched).

1. `chore: scaffold KAIROS v0.1 project (plan, pyproject, package skeleton)`
2. `feat: domain layer, schema, FTS5 migration, database engine`
3. `feat: filesystem workspace, content store, git metadata reader`
4. `feat: corpus-native parsers (text/markdown, pdf, json, kconfig, logs, repository)`
5. `feat: services and CLI commands (init, ingest, artifacts, show, search, trace, note, well, config, logs, doctor)`
6. `test: fixtures, unit and integration test suite`
7. `docs: architecture, cli reference, v0.1 status, demo script`

Each stage is committed only after its own code runs (parsers are tested as
they're written; CLI commands are smoke-tested against a real temp
workspace per the vertical-slice checkpoint below) — commits are a record of
working states, not a batching convenience.

## 8. Build order (vertical slice first)

To surface SQLAlchemy/FTS5/Alembic integration issues early rather than at
the end of a 35-file build:

1. Domain layer + DB schema/migration + content store + text/markdown parser
   only.
2. Wire and **actually run** `init`, `ingest`, `artifacts`, `show`, `search`
   end-to-end against a real temp workspace.
3. Broaden: remaining 5 parsers, then `trace`, `note`, `well`, `config`,
   `logs`, `doctor`.
4. Full test suite, lint/typecheck pass, docs, demo script.
