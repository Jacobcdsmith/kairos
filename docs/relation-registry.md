# KAIROS Relation Registry

Every row in the `relations` table is a typed, explicit, machine-derived
edge — never a similarity guess. This registry inventories every predicate
KAIROS v0.1 can produce: who creates it, what it connects, what evidence
backs it, and how deterministic it is. `tests/unit/test_relation_registry_consistency.py`
enforces the "evidence requirement" and "determinism guarantee" columns
against every parser's actual output, so this table can't silently drift
from the code.

All seven predicates below are created with `origin = derived` and a
non-empty `derivation_rule` — no exceptions exist in v0.1. See
[docs/architecture.md](architecture.md#the-provenance-model) for what
`derived` means relative to `raw`/`extracted`/`user`.

| Predicate | Subject kind | Object kind | Parser / rule | Evidence requirement | Determinism | Known limitations |
|---|---|---|---|---|---|---|
| `heading_contains` | entity (heading) | span | Markdown/Text — `markdown.heading_containment.v1` | `evidence_span_id` = the heading's own span | Fully deterministic: nesting is purely lexical (heading level + document order), no fuzzy matching | A span nests under the *nearest preceding* heading of a shallower level; it does not detect content that is logically misplaced relative to its heading |
| `page_precedes` | span (page) | span (page) | PDF — `pdf.page_sequence.v1` | none (`evidence_span_id = None`) — the relation *is* the physical page order, which needs no separate citation | Fully deterministic: page order as read from the PDF's page list | Says nothing about page *content* continuity, only physical sequence |
| `json_contains` | span (container) | span (any) | JSON — `json.tree_containment.v1` | `evidence_span_id` = the parent container's own span | Fully deterministic: exact JSON tree structure | None — this is a lossless structural mirror of the parsed document |
| `menu_contains` | span (menu/symbol) | span (menu/symbol) | Kconfig menu — `kconfig.menu_containment.v1` | `evidence_span_id` = the child's own span | Fully deterministic: exact `children` array structure in the source JSON | None |
| `depends_on` | entity (kconfig_symbol) | entity (kconfig_symbol) | Kconfig menu — `kconfig.depends_on.v1` | none (`evidence_span_id = None`) — the dependency is between two *entities*, not spans; the owning symbol's span carries the raw `depends_on` text in its metadata | Deterministic **only** for a bare identifier or an `A && B && ...` conjunction of identifiers; anything with `\|\|`, `!`, `=`, or parentheses is **not** decomposed into a relation — it is kept verbatim on the span's metadata and flagged with a `Diagnostic` instead of guessed at | A dependency on a symbol that was never ingested produces no relation at all (silently skipped, by design — see `kconfig.py`'s `pending_depends` resolution); it is not treated as broken, since the target may simply not exist in this workspace yet |
| `log_in_session` | entity (log_session) | span (log_line) | Logs — `log.session_membership.v1` | `evidence_span_id` = the line's own span | Fully deterministic: every line between one `=== label ===` boundary and the next belongs to that session | The boundary marker line itself is *not* included in this relation (it has its own `mentioned_in` edge to the session entity instead — see below) |
| `imports` | entity (module) | entity (module) | Python AST — `python.import.v1` | `evidence_span_id` = the `import`/`from...import` statement's own span | Deterministic **by name only** — `import foo` links to whichever entity has `canonical_name == "foo"` after cross-artifact reconciliation, regardless of where that module actually lives on disk. Two unrelated modules that happen to share a bare name will be treated as the same import target | This is a documented, deliberate simplification (see architecture.md and README known limitations), not a bug — v0.1 has no path-aware import resolution |

## `mentioned_in` — extracted, not derived

`trace` also renders entity↔span edges labeled `mentioned_in`. These come
from the `mentions` table, not `relations`, and are always tagged `layer =
extracted` (hardcoded in `kairos.services.trace`, correctly — `mentions` has
no `origin` column at all, because a mention **is** the direct, deterministic
evidence link a parser records at extraction time; there is no "derived"
or "user" variant of it in v0.1). Every entity-creating parser
(Markdown/Text, Kconfig, Python AST, and Logs as of this audit — see
finding 6.1 in [docs/v0.1-audit.md](v0.1-audit.md)) creates at least one
`Mention` grounding every entity it emits to the exact span it came from.

## `user`-origin relations: not yet possible

Nothing in v0.1 ever writes a `relations` row with `origin = user`. The only
owner-authored tables are `notes` and `well_members`, neither of which is a
`relations` row. `kairos trace`'s edge rendering reads the real `origin`
column off each relation (not a hardcoded assumption — see the audit's
finding 4.2), so if a future milestone ever lets an owner assert a direct
connection between two objects, it will render correctly as `layer=user`
without further changes here. Today, "differentiates a user-authored
connection" is vacuously true: there is nothing to mislabel.

## What `trace` will never show

No predicate above is based on textual similarity, embeddings, or
co-occurrence — every edge is backed by either an evidence span (an exact
citation) or, for `page_precedes`/`depends_on`, an unambiguous structural or
textual fact from the source (physical page order; an exact identifier
match). Two terms that merely *look* similar (e.g. a heading called
`"Widget"` and a different heading called `"Widgets"`) are never linked:
entity reconciliation (`kairos.services.ingest._reconcile_entity`) matches
on exact, case-sensitive `canonical_name` plus `entity_type` — never a fuzzy
or prefix match. See `tests/integration/test_no_false_relations.py`.
