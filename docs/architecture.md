# KAIROS v0.1 Architecture

## Storage layout

Every KAIROS workspace is a directory containing a `.kairos/` control
directory. All KAIROS writes are confined to this directory; source
material outside it is never modified.

```
<workspace>/
  .kairos/
    kairos.db        # SQLite — the canonical durable store
    events.jsonl      # append-only mirror of the `events` table
    config.json        # workspace name, creation time, schema version
    content/
      <sha256[:2]>/<sha256>   # raw ingested bytes, content-addressed, read-only
```

`kairos init <workspace>` creates this layout and runs the Alembic
migration to head. Everything else — `ingest`, `search`, `show`, `trace`,
`note`, `well`, `config`, `logs`, `doctor` — operates against an existing
workspace, discovered by walking up from the current directory looking for
`.kairos/`.

## The provenance model

The framework must distinguish four kinds of content, and nothing may
masquerade as source truth:

| Layer         | What it is                                              | Example                              |
|---------------|----------------------------------------------------------|---------------------------------------|
| **raw**       | The ingested bytes themselves                            | The original `.md` / `.pdf` / `.py` file, in `content/` |
| **extracted** | Deterministic parser output                               | A `source_spans` row; an entity a parser emits directly |
| **derived**   | A machine-made link between already-extracted objects      | A `relations` row (e.g. `heading_contains`, `imports`) |
| **user**      | Owner-authored                                            | A `notes` row; `well_members` |
| *(model)*     | *Reserved for a future milestone. Nothing in v0.1 writes this.* | — |

Every artifact's `metadata_json` records how it got here: `parser_name`,
`parser_version`, `parse_status`. Every `entities`/`relations` row carries
an `origin` column with exactly the vocabulary above (`raw` never appears
there — artifacts *are* the raw layer, entities/relations are not raw by
construction).

### The provenance envelope

Every CLI-facing result — a search hit, a trace node, a `show` span, a
`config`/`logs` lookup — is wrapped in one shared shape
(`kairos.schemas.provenance.ProvenanceEnvelope`):

```
artifact_id       — the artifact this came from
source_path       — workspace-relative (or absolute, if outside the
                     workspace) path to the original file
artifact_kind     — text | markdown | pdf | json | kconfig | log |
                     repository_file
locator           — a discriminated union, exact to the source kind (below)
locator_str       — that locator's compact string form, e.g. "lines:10-14";
                     round-trips through `kairos show --locator <str>`
parser_name       — e.g. "kairos.markdown"
parser_version    — e.g. "1.0.0"
layer             — "raw" | "extracted" | "derived" | "user"
```

### Locators, one discriminated union per source kind

| `locator_kind`     | String form                          | Used by |
|--------------------|----------------------------------------|---------|
| `pdf_page`         | `page:12`                              | PDF |
| `line_range`        | `lines:10-14`                          | text/Markdown |
| `json_path`         | `json:$.a.b[2]`                        | JSON |
| `kconfig_symbol`     | `kconfig:Main/Networking/CONFIG_WIFI`  | Kconfig menu |
| `repo_file_lines`   | `repo:src/foo.py:10-14`                | repository/Python |
| `log_event`         | `log:1723:2024-01-01T00:00:03Z`        | logs |

## Schema

Nine tables, used verbatim (column names unchanged from the spec):
`artifacts`, `source_spans`, `entities`, `mentions`, `relations`, `notes`,
`coherence_wells`, `well_members`, `events`.

Additions, not deviations:

- **`source_spans_fts`** — an FTS5 virtual table indexing
  `source_spans.text_content`, with `span_id`/`artifact_id`/`span_kind` as
  `UNINDEXED` join/filter columns. It is **not** an ORM model — autogenerate
  can't see virtual tables — so it's hand-written DDL in the single Alembic
  migration (`0001_initial_schema.py`), and it's queried only through
  `kairos.infrastructure.database.fts` via SQLAlchemy Core `text()`.
- **Sync triggers** — `source_spans_fts_ai/au/ad`, created in the same
  migration, keep the index in lockstep with `source_spans` on every
  insert/update/delete. No code path can write a span without the index
  following, because the trigger — not application code — does the sync.
- Standard B-tree indexes on the obvious join/filter columns (`artifact_id`,
  `parent_span_id`, `entity_id`, `subject_id`/`object_id`, `well_id`, etc).

Migrations run via `alembic.command.upgrade`, invoked programmatically by
`kairos init` — never as a subprocess. v0.1 ships exactly one migration.

### FTS5 tokenization and ranking

`source_spans_fts` uses FTS5's default `unicode61` tokenizer: Unicode-aware
word splitting and case folding, no stemming (`"widget"` and `"widgets"` are
different tokens; `"Widget"` and `"widget"` are the same one). Ranking is
FTS5's built-in `bm25()` over the single indexed column
(`text_content`) — with one column there is no cross-column weighting to
configure. `kairos doctor`'s `fts_consistency` check (added in the v0.1
audit — see [docs/v0.1-audit.md](v0.1-audit.md)) confirms `source_spans` and
`source_spans_fts` agree in row count and that every FTS row's `span_id`
resolves to a live span; `kairos search` independently skips any FTS hit
whose backing span or artifact row is missing rather than surfacing a
dangling reference.

## Parser registry

`kairos.infrastructure.parsers.registry.ParserRegistry` picks a parser by
extension first (`.md`/`.markdown`, `.txt`, `.json`, `.log`/`.logs`, `.py`,
`.pdf`), falling back to content sniffing for extension-less files (PDF
magic bytes; JSON structural sniffing). **Kconfig-menu JSON is a JSON
document with a `"kairos_kind": "kconfig_menu"` top-level key** — the
`KconfigParser` is checked before the generic `JsonParser` for exactly this
reason; a Kconfig-shaped document would otherwise also parse as valid JSON.

Every parser implements one shared interface
(`kairos.domain.parser.Parser`):

```python
class Parser(Protocol):
    kind: ArtifactKind
    parser_name: str
    parser_version: str
    def sniff(self, path: Path) -> bool: ...
    def parse(self, path: Path, artifact_id: str) -> ParseResult: ...
```

`ParseResult` bundles spans, entities, mentions, relations, diagnostics,
and a `parse_status` (`ok` / `partial` / `failed`). **A parser never
raises to signal malformed input** — it downgrades `parse_status` and
records a `Diagnostic`, returning whatever it could recover. Ingest persists
diagnostics onto the artifact's `metadata_json`; nothing is silently
dropped.

Each parser emits at least one *derived relation* kind, so `trace` has
edges to walk, not just a flat list of spans:

| Parser | Derived relation(s) | Notes |
|---|---|---|
| Markdown/Text | `heading_contains` (heading entity -> child span) | Every heading is also a `mention` of its own entity — the same heading text repeated across documents resolves to the same entity row, which is what lets `trace` cross document boundaries. |
| PDF | `page_precedes` (page span -> next page span) | Pages with no extractable text still get a span (empty text) plus a diagnostic. |
| JSON | `json_contains` (container span -> child span) | Raw bytes are untouched in `content/`; every scalar *and* container gets a span at JSON-path granularity. |
| Kconfig menu | `menu_contains` (span -> span), `depends_on` (symbol entity -> symbol entity) | `depends_on` is only decomposed into relations for a simple identifier or a `&&` conjunction of identifiers — anything else stays as raw text on the span, flagged with a diagnostic. Fields this parser doesn't model (e.g. a project-specific `help` string) are preserved verbatim under the span's `metadata["extra"]`, never dropped. A non-object entry in a `children` array is diagnosed (`parse_status` downgrades to `partial`), not silently skipped. |
| Logs | `log_in_session` (session entity -> line span) | Session boundaries are `=== <label> ===` marker lines; the boundary line itself gets its own span and a `mention` grounding the session entity to it (session entities are otherwise the only entity kind with no evidence trail). Lines that don't match the log-line pattern still get a span, flagged with a diagnostic. |
| Repository (Python AST) | `imports` (module entity -> imported-module entity) | Resolution is by name via the same cross-artifact entity dedup as headings — an import only becomes a *meaningful* link once a module of that name is actually ingested; nothing is guessed. Module, class, and function entities are each grounded by a `mention` to their own defining span, same as every other entity-creating parser. |

### Cross-artifact entity reconciliation

Parsers never talk to the database — they emit fresh `Entity` objects with
their own throwaway ids. The **ingest service**
(`kairos.services.ingest._reconcile_entity`) is the only place that
resolves identity: before inserting a parser-emitted entity, it looks for
an existing `entities` row with the same `(canonical_name, entity_type)`
and reuses it if found, remapping every mention/relation that referenced
the parser's temporary id. This is the entire mechanism behind cross-
document `trace`: two Markdown files with the same `# Widgets` heading, or
two Python files each importing `os`, end up pointing at the *same* entity
row.

## Trace: bidirectional, evidence-first traversal

`kairos trace <term-or-id>` seeds from (in order): an exact artifact id, an
exact span id, an entity whose `canonical_name` matches (case-insensitive),
or — failing all of those — the direct FTS5 hits for the query text.

From the seed set, breadth-first traversal follows both `relations` *and*
`mentions`, **in both directions**: a relation's object can lead back to
its subject, and a span can climb up to the entities it mentions just as an
entity can walk down to every span that mentions it. This bidirectionality
is what lets a bare word inside a paragraph (no entity of its own) climb up
to a shared heading entity and back down into a *different* artifact,
crossing document boundaries in a couple of hops — proven by an integration
test with two Markdown files sharing a `# Widgets` heading. Depth is capped
by `--depth`; a visited-set prevents cycles from repeating edges/nodes.

## Event model

Every command that mutates the workspace appends one event, in two places
kept consistent by `kairos.services.events.append_event`:

1. An `events` row (queryable via SQL, joined with everything else).
2. A line in `.kairos/events.jsonl` (`{id, occurred_at, event_type,
   payload}`) — a reproducible, SQLite-independent record of what
   happened, in ingest order.

Event types in v0.1: `workspace.init`, `ingest.run`, `note.add`,
`well.create`, `well.add`, `well.remove`.

## Read-only boundary

KAIROS is read-only with respect to registered source material:

- `ContentStore.put` copies bytes into `content/<hash>` and chmods the
  copy read-only; if the same bytes are ingested again, the existing copy
  is left untouched (write-once, verified by `test_content_store.py`).
- Nothing in the codebase opens an ingested source path for writing.
- The only writes KAIROS ever performs to owner data are **additive**:
  user notes (`notes`) and well membership (`well_members`) — never
  overwriting or reinterpreting the source itself.
- Git metadata (`kairos.infrastructure.git.metadata`) is read via
  `git rev-parse` / `git remote -v`, never via a mutating command, and
  failures are non-fatal (ingest proceeds without it).

## The TUI presentation layer (v0.2-alpha)

`kairos tui` (`src/kairos/tui/`) is a fourth presentation surface alongside
the CLI, not a new layer in the `domain -> infrastructure -> services ->
cli` chain:

```
Textual widgets/screens (kairos/tui/{app,screens,widgets}.py)
      -> kairos.tui.controller.dispatch_text
      -> exactly one kairos.services.* function per command
      -> existing domain/infrastructure layers, unchanged
```

Rules this boundary enforces:

- **Textual is optional and isolated.** Only `kairos/tui/` and
  `kairos/cli/commands/tui.py` (lazily, inside `run()`) may import
  `textual`. `tests/unit/test_architecture_boundaries.py::test_only_kairos_tui_imports_textual`
  enforces this the same way the domain-layer import test does.
- **No direct SQL/FTS/ORM access from the TUI.** `kairos.tui.controller`
  calls only typed `kairos.services.*` functions, each already returning
  a `ProvenanceEnvelope`-carrying result (`SearchResult`, `TraceResult`,
  `ArtifactDetail`, ...). The one gap found during implementation —
  reading recent local activity — was filled with a minimally-typed
  service (`kairos.services.activity.recent_events`), not a query written
  inside the TUI.
- **State is explicit and immutable.** `kairos.tui.state.TuiState` is a
  frozen dataclass; `dispatch_text` returns a new one rather than mutating
  widget-internal state. This makes `kairos.tui.controller` unit-testable
  without a Textual `Pilot` at all (`tests/tui/test_controller.py`).
- **Mutation surface is a strict subset of the CLI's.** The controller can
  only call `add_note` and read/activate/clear a well — never
  `create_well`, `add_member`, or anything ingest-related. See
  [docs/tli.md](tli.md) for the exact command grammar and
  [docs/tli-implementation-plan.md](tli-implementation-plan.md) for the
  full design rationale, including where it deliberately deviates from an
  initial spec (well lookup by name instead of id; a dedicated `"notes"`
  mode instead of overloading `"show"`).

## Non-goals (v0.1)

Out of scope for this milestone, by design: hardware/embedded systems,
device clients, simulations or virtual companions, remote node management,
external messaging integrations, cloud services, multi-agent
orchestration, autonomous background execution, self-modification, and
model inference or model-provider integration. Embeddings and vector
similarity are also out of scope — FTS5 and structured `relations`/
`mentions` traversal are the retrieval foundation. See
[docs/v0.1-status.md](v0.1-status.md) for what a later milestone might
still add within this same local-framework scope.
