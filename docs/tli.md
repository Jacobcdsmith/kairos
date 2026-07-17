# KAIROS Terminal Lineage Interface (TLI) — v0.2-alpha

## What it is

`kairos tui` is a full-screen, keyboard-first Textual application that
presents the same v0.1 services (`search`, `show`, `trace`, `config`,
`logs`, `doctor`, `note`, `well`) as a persistent, three-pane terminal
workspace instead of one-shot CLI invocations. It is meant to feel like a
serious operator tool — dense, immediate, command-driven — not a
dashboard and not a chat interface.

## What it is not

- Not a chatbot. The command line only ever accepts the fixed grammar
  below (`:search`, `:trace`, ...); free-form text that doesn't start with
  `:` (or the bare `?` alias) is rejected with a usage error, not
  interpreted.
- Not an LLM surface. No model inference, no embeddings, no
  similarity-based ranking anywhere in this interface.
- Not a new substrate. Every result comes from an existing
  `kairos.services.*` function; the TUI adds one small read-only service
  (`kairos.services.activity.recent_events`) and no new tables, no new
  relation types, no new storage.
- Not a mutation surface beyond what the CLI already does. The only writes
  this alpha can make are `note add` and well activation
  (`:well use`/`:well clear`) — not well creation or membership changes,
  which stay CLI-only in this milestone.

## Installation

```bash
pip install -e ".[tui]"
```

The base `kairos` install and every other command work with this extra
absent. `kairos tui` without it prints an install message and exits 1 —
it never raises an import traceback.

## Launch

```bash
kairos tui
```

Run from inside (or under) an initialized workspace, same as any other
`kairos` command.

## Layout

```
┌ KAIROS — workspace: my-corpus — well: none — LOCAL / OFFLINE ┐
│  EXPLORER          WORKSPACE                  EVIDENCE        │
│  (what you can      (transcript of every       (full citation │
│   navigate to)       command run this          for whatever   │
│                      session)                  is selected)   │
├────────────────────────────────────────────────────────────────┤
│ :search provenance                                              │
├────────────────────────────────────────────────────────────────┤
│ ↑↓ select · Enter inspect · Tab pane · / search · w wells · ...│
└────────────────────────────────────────────────────────────────┘
```

Responsive to terminal width:

- **>=120 columns**: all three panes visible.
- **80-119 columns**: Explorer + Workspace; Evidence is still reachable
  by Tab-cycling into it (it becomes the focused, visible pane) — its
  content is never truncated, just not shown side-by-side by default.
- **<80 columns**: only Explorer/Evidence are hidden by default; Workspace
  (the transcript) always shows full, untruncated citations regardless of
  width.

## Command language

```
:home                       recent local activity
:artifacts [kind]           list ingested artifacts
:search <query>             full-text search (alias: :s)
:show <artifact-id> [loc]   structured source detail
:trace <term-or-id>         explicit-relation traversal (alias: :t)
:well list                  all coherence wells
:well use <name>            set the active well (search/trace filter)
:well clear                 clear the active well
:well show <name>           one well's members
:config <symbol>            Kconfig symbol lookup
:logs <query>               log search with locators
:doctor                     workspace health checks (inspect only)
:note list <target-id>      notes on an artifact or span
:note add <target-id> <text>  add a note (the only free-text mutation)
:history                    this session's command log
:help  (or bare ?)          help overlay
:refresh  (or key r)        re-run the last successful command
:quit  (or :q)              quit
```

Unknown commands produce an actionable error naming the closest valid
command — never a traceback.

## Keybindings

| Key | Action |
|---|---|
| `Ctrl+P` | Focus the command line |
| `Ctrl+R` | Open the history overlay |
| `Tab` / `Shift+Tab` | Cycle focus: Explorer → Workspace → Evidence → command line |
| `Enter` | Run a command, or inspect the highlighted Explorer item |
| `Up` / `Down` | Move the Explorer selection |
| `/` | Start a `:search ` in the command line |
| `w` | Open the coherence-well picker |
| `c` | Copy the current citation (plain text, terminal clipboard escape — no shell command) |
| `y` | Copy the current source excerpt (same mechanism as `c`) |
| `r` | Re-run the last successful command (not while typing) |
| `?` | Help overlay |
| `q` | Quit (not while the command line has focus) |
| `Escape` | Close an overlay |

`c`/`y` use the terminal's own clipboard escape sequence (OSC 52) — never
a shell command. Some terminals don't support it and the write silently
no-ops, so both keys always also echo the copied text into the Workspace
transcript, which is the reliable fallback regardless of clipboard support.

## Provenance legend

| Layer | Meaning |
|---|---|
| RAW | The ingested bytes themselves |
| EXTRACTED | Deterministic parser output (a span, an entity) |
| DERIVED | A machine-made link between already-extracted objects |
| USER | Owner-authored (a note, a well membership) |

Every result carries a full citation: artifact id, source path, exact
locator, parser + version, and one of the four layers above — the same
`ProvenanceEnvelope` the CLI uses (see
[docs/architecture.md](architecture.md#the-provenance-model)). A `trace`
edge marked DERIVED always names its `derivation_rule`, and the Evidence
pane states explicitly that it is a deterministic rule match, not a
semantic-similarity claim.

## Active-well behavior

The header always shows the active well (`well: none` or `well: <name>`).
When a well is active, `:search` and `:trace` are scoped to it, matching
the CLI's `--well` flag exactly. `:logs` and `:config` are **not**
well-scoped in this alpha — the underlying services
(`query_logs`/`get_config_symbol`) don't take a well parameter, and this
interface does not pretend otherwise. Activating/clearing a well from the
`w` picker never changes well membership; that stays a CLI-only operation
(`kairos well add`/`kairos well remove`).

## Limitations (v0.2-alpha)

- `:well create` and `:well add`/`:well remove` are not available from the
  TUI — use the CLI for those; the picker (`w`) can only activate or clear
  an already-existing well.
- `doctor` is inspect-only; there is no repair action anywhere in this
  interface.
- `:logs`/`:config` do not honor the active well (see above).
- The narrow (<80 column) layout hides Explorer and Evidence by default
  rather than offering a dedicated single-pane navigation screen for each;
  Tab-cycling still reaches them.
- History replay (`Ctrl+R`) shows past commands and their status but does
  not yet re-run a selected historical entry directly from the overlay —
  use `:refresh` (or `r`) to re-run the most recent successful command.

## Troubleshooting

**`kairos tui` prints an install message and exits.** Textual isn't
installed. Run `pip install -e ".[tui]"` and try again.

**The interface looks wrong / wrapped oddly in a very narrow terminal.**
Resize to at least 80 columns for two panes, 120 for all three. Below
that, only the Workspace pane is shown; nothing is truncated, but the
Explorer/Evidence content is reachable only via Tab-cycling.

**A command says "Unknown command."** Commands must start with `:` (or be
the bare `?` alias for `:help`). Check `:help` for the exact grammar.
