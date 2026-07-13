# KAIROS CLI Reference

All commands return a non-zero exit code on failure, with a message on
stderr prefixed `Error:`. Table/panel output uses [Rich](https://github.com/Textualize/rich);
IDs are always shown in full (never truncated), since every result must
expose its exact provenance.

## Exit codes

| Code | Meaning | Examples |
|---|---|---|
| `0` | Success | |
| `1` | Expected user/input/domain failure | Unknown artifact/well/note-target id, a bad locator string, an unrecognized file kind, a malformed FTS5 query, a duplicate well name, an unknown Kconfig symbol |
| `2` | Workspace/configuration/integrity failure | No `.kairos/` found, `init` on a directory that already has one, any failing `kairos doctor` check (broken schema, tampered content, a drifted search index) |
| `3` | Unexpected internal error (a real bug, not user input) | Prints a short message and suppresses the traceback by default |

Set `KAIROS_DEBUG=1` in the environment to get the full Python traceback for
a code-3 failure instead of the short message — useful when filing a bug
report, not needed for normal use.

---

## `kairos init <workspace>`

Create a new workspace: `.kairos/` control directory, SQLite database
migrated to the current schema, empty `events.jsonl`.

```
$ kairos init ./my-workspace
Initialized KAIROS workspace at /path/to/my-workspace
  database: /path/to/my-workspace/.kairos/kairos.db
  events:   /path/to/my-workspace/.kairos/events.jsonl
```

Options: `--name TEXT` (human-readable workspace name; defaults to the
directory name). Fails if `.kairos/` already exists there.

---

## `kairos ingest <path> [--recursive]`

Ingest one file, or (with `--recursive`) every file in a directory tree.
The parser is chosen by extension, falling back to content sniffing. Bytes
are hashed and stored once; re-ingesting identical content is a no-op that
reports `already ingested`.

```
$ kairos ingest sample.md
                                   Ingested
┌──────────────────┬──────────────────────┬──────────┬────────┬───────┬──────┐
│ id               │ path                 │ kind     │ status │ spans │ note │
├──────────────────┼──────────────────────┼──────────┼────────┼───────┼──────┤
│ 22437b14d8df46dc…│ /abs/path/sample.md  │ markdown │ ok     │     6 │      │
└──────────────────┴──────────────────────┴──────────┴────────┴───────┴──────┘
```

If the parser recorded diagnostics (malformed-but-recoverable content),
they're listed below the table and `status` shows `partial` or `failed` —
never silently dropped.

---

## `kairos artifacts [--kind <kind>] [--limit N]`

List ingested artifacts, most recent first. `--kind` filters by
`text | markdown | pdf | json | kconfig | log | repository_file`.

```
$ kairos artifacts --kind markdown
```

---

## `kairos show <artifact-id> [--locator <locator>]`

Full parsed detail for one artifact: every span, each in its own panel
titled with its kind, locator, and provenance layer.

```
$ kairos show 22437b14d8df46dcb0a71e110cf40c2b
┌───────────────────────────────── Artifact ──────────────────────────────────┐
│ id: 22437b14d8df46dcb0a71e110cf40c2b                                        │
│ path: sample.md                                                            │
│ kind: markdown                                                              │
│ parser: kairos.markdown v1.0.0                                             │
│ parse_status: ok                                                           │
└──────────────────────────────────────────────────────────────────────────────┘
┌────────────────────────  lines:1-1  layer=extracted ────────────────────────┐
│ Widgets                                                                    │
└─────────────────── span_id=1106b6a9d8f94dd6b83bf593e36c7e8d ────────────────┘
```

`--locator lines:1-1` (or `page:3`, `json:$.a.b`, `kconfig:Main/CONFIG_X`,
`repo:src/foo.py:10-14`, `log:42:2024-01-01T00:00:00Z`) restricts output to
spans matching that exact locator.

---

## `kairos search <query> [--kind <kind>] [--well <name>] [--limit N]`

FTS5 full-text search over span text, ranked by BM25. `--kind` filters by
`span_kind` (`heading`, `paragraph`, `pdf_page`, `log_line`, ...). `--well`
scopes to a coherence well's member artifacts.

```
$ kairos search widget
                               Search: "widget"
┌─────────────────┬────────────────┬────────────┬───────────┬────────────────┐
│ artifact_id     │ path           │ locator    │ layer     │ snippet        │
├─────────────────┼────────────────┼────────────┼───────────┼────────────────┤
│ 22437b14...     │ sample.md      │ lines:3-3  │ extracted │ The [widget]   │
│                 │                │            │           │ system handles │
└─────────────────┴────────────────┴────────────┴───────────┴────────────────┘
```

FTS5 query syntax applies: `()`, `-`, `"`, bare `AND`/`OR`/`NEAR` are
operators. A malformed query (e.g. unbalanced parens) exits non-zero with
an actionable message rather than a traceback.

---

## `kairos trace <term-or-id> [--depth N] [--well <name>]`

Evidence-first traversal. Seeds from (in priority order) an exact artifact
id, an exact span id, an entity name match, or FTS5 hits. Walks
`relations` and `mentions` in both directions up to `--depth` hops (default
2), printing every node reached and every edge crossed (with its
`derivation_rule` and provenance).

```
$ kairos trace Widgets --depth 2
                                            Trace nodes: "Widgets"
┌────────┬──────────────────────┬─────────────────────┬──────────────────────┬─────────────┬───────────┬───────────┐
│ kind   │ id                   │ label               │ artifact_id           │ source_path │ locator   │ layer     │
├────────┼──────────────────────┼─────────────────────┼──────────────────────┼─────────────┼───────────┼───────────┤
│ entity │ bbdddf4863ef4237...  │ Widgets             │                       │             │           │           │
│ span   │ 6d29e4451de5442d...  │ The widget system...│ 22437b14d8df46dc...  │ sample.md   │ lines:3-3 │ extracted │
└────────┴──────────────────────┴─────────────────────┴──────────────────────┴─────────────┴───────────┴───────────┘
                                  Trace edges
┌────────────────┬───────────────┬────────────────┬───────────┬───────────────┐
│ subject        │ predicate     │ object         │ layer     │ rule          │
├────────────────┼───────────────┼────────────────┼───────────┼───────────────┤
│ entity:bbdd... │ heading_cont… │ span:6d29e4... │ derived   │ markdown.hea… │
└────────────────┴───────────────┴────────────────┴───────────┴───────────────┘
```

A term with no entity of its own — a bare word inside a paragraph — can
still cross into a *different* artifact within a couple of hops, by
climbing up to a heading (or module, or Kconfig menu, or log session)
entity two documents share, then back down.

---

## `kairos note add <target-id> <text>` / `kairos note list <target-id>`

Owner-authored notes on an artifact or a span — stored separately from
source and extraction (`origin = user`).

```
$ kairos note add 22437b14... "revisit after v0.2"
Added note 17c8a7e7140e49628ab2abfc6684d128 on artifact 22437b14...

$ kairos note list 22437b14...
```

---

## `kairos well create <name> --purpose <text>`

Create a coherence well: a deliberate, owner-curated working set.

```
$ kairos well create widget-work --purpose "Everything about the widget system"
Created well widget-work (80d90b80223348a889cb0f2b9003145d)
```

## `kairos well add <well-name> <artifact-or-span-id> [--note <text>]`

Add an artifact or span to a well. Idempotent: adding the same target
twice returns the existing membership rather than duplicating it.

## `kairos well remove <well-name> <member-id>`

Remove a membership by its own id (from `well show`, **not** the target's
own artifact/span id).

## `kairos well show <well-name>`

```
$ kairos well show widget-work
widget-work — Everything about the widget system (1 members)
┌────────────────────────┬─────────────┬────────────────────────┬─────────────┐
│ member_id              │ target_kind │ target_id              │ note        │
├────────────────────────┼─────────────┼────────────────────────┼─────────────┤
│ 25993c7e964342b5b345…  │ artifact    │ 1d4210ac6ec34f80a9f3…  │ primary doc │
└────────────────────────┴─────────────┴────────────────────────┴─────────────┘
```

## `kairos well list`

List every coherence well with its member count.

---

## `kairos config <symbol>`

Look up one Kconfig symbol by name (from an ingested Kconfig-menu JSON
document): prompt, type, default, `depends_on`, choices, child symbols,
and exact provenance.

```
$ kairos config CONFIG_WIFI_POWER_SAVE
┌────────────────────────── CONFIG_WIFI_POWER_SAVE ───────────────────────────┐
│ prompt: WiFi power save                                                    │
│ type: bool                                                                 │
│ default: n                                                                 │
│ depends_on: CONFIG_WIFI                                                    │
│ choices: (none)                                                           │
│ children: (none)                                                         │
│ locator: kconfig:Main/Networking/CONFIG_WIFI_POWER_SAVE  layer=extracted  │
│ source: sample_menu.json                                                  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## `kairos logs <query> [--before N] [--after N] [--level <level>]`

FTS5 search over ingested log lines, with `N` lines of context before/after
each match and an optional exact `--level` filter (applied to the match
itself; context lines are shown regardless of their own level).

```
$ kairos logs connection --level ERROR
$ kairos logs widget --before 1 --after 1
```

---

## `kairos doctor`

Environment and workspace health checks: FTS5 actually compiled into this
Python's `sqlite3` (the one failure that would otherwise break every
ingest/search silently), workspace root present, schema migration applied,
content store and event log reachable. Exits non-zero if any check fails.

```
$ kairos doctor
                                 kairos doctor
┌──────────────────┬────────┬─────────────────────────────────────────────────┐
│ check            │ status │ detail                                          │
├──────────────────┼────────┼─────────────────────────────────────────────────┤
│ fts5_available   │ ok     │ FTS5 is compiled into this Python's sqlite3.    │
│ workspace_root   │ ok     │ /path/to/workspace                              │
│ schema_migration │ ok     │ alembic_version='0001'                          │
│ content_store    │ ok     │ /path/to/workspace/.kairos/content              │
│ events_log       │ ok     │ /path/to/workspace/.kairos/events.jsonl         │
└──────────────────┴────────┴─────────────────────────────────────────────────┘
```
