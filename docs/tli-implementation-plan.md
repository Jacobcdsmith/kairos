# KAIROS v0.2-alpha — Terminal Lineage Interface (TLI) implementation plan

Written before implementation, per the workflow this milestone follows.
This is a plan, not a status report — see
[v0.2-alpha-status.md](v0.2-alpha-status.md) for what actually landed.

## What this milestone is

`kairos tui` — a full-screen, keyboard-first Textual presentation layer
over the existing v0.1 service layer. It is read-mostly: it can invoke the
same note/well-membership writes the CLI already exposes, and nothing
else. It adds no new domain logic, no new storage, no new relation types,
and no model of any kind.

## What this milestone is not

Not a chatbot, not an LLM surface, not a web UI, not a daemon, not a
network service, not a source-mutation tool, not a semantic/embedding
search layer. See the non-goals section below for the exhaustive list.

## Dependency strategy

Textual is an **optional** extra:

```toml
[project.optional-dependencies]
tui = ["textual>=0.58,<1.0"]
```

- `kairos/tui/` is the only package allowed to `import textual`.
- `kairos/cli/commands/tui.py` imports Textual **inside the command
  function**, not at module scope, so `from kairos.cli.commands import tui`
  (which `main.py` does unconditionally) never fails when Textual isn't
  installed.
- If the import fails, `kairos tui` prints an actionable install message
  (`pip install -e ".[tui]"` / `pip install kairos[tui]`) and exits with
  the existing "expected user error" exit code (1), not a traceback.
- No other module under `src/kairos/cli`, `src/kairos/services`,
  `src/kairos/domain`, or `src/kairos/infrastructure` imports `textual` or
  `kairos.tui`.

## Package layout

```
src/kairos/tui/
  __init__.py
  app.py                 # KairosApp(App): screens, bindings, layout wiring
  state.py                # Selection, ActivityEntry, TuiState (frozen dataclasses)
  controller.py            # dispatch: command -> service call -> new TuiState
  commands.py              # command grammar: parse ":search x" etc. into a Command
  history.py               # in-memory activity log + Ctrl+R search helper
  styles/kairos.tcss
  screens/
    main.py                 # three-pane workspace + command line + status line
    help.py                  # help/legend overlay
    well_picker.py            # well selector overlay (activate/clear only)
  widgets/
    explorer_pane.py
    workspace_pane.py         # combines "activity transcript" behavior
    evidence_pane.py
    command_line.py
    status_line.py
```

The suggested `context_pane.py` / `provenance_block.py` / `relation_tree.py`
/ `result_list.py` / `event_log.py` / `activity_pane.py` /
`command_palette.py` from the spec are folded into fewer, real files
instead of stub files with no content: the "activity pane" behavior lives
inside `workspace_pane.py`, the provenance block and relation tree are
render helpers inside `evidence_pane.py`, and a full "command palette"
screen distinct from the always-visible command line is not built in this
alpha (`:help` plus the command line already covers discovery). This
keeps every shipped file doing real work.

## Service-layer gaps identified before implementation

The TUI must not touch SQL/FTS/ORM directly. Three gaps exist between
what the spec's Explorer pane wants and what `kairos/services/*` exposes
today; smallest-typed-method fixes, added under `services/`, not worked
around from the TUI:

1. **Recent local activity.** `services/events.py` only has
   `append_event`. `infrastructure/database/repositories.list_events`
   already exists. Add `services/activity.py::recent_events(ctx, limit)`
   returning a small typed `ActivityEvent` schema (id, occurred_at,
   event_type, payload) — a thin read wrapper, not new logic.
2. **Well-scoped search/trace only.** `search()` and `trace()` already
   take `well: str | None`. `query_logs()` and `get_config_symbol()` do
   not. The plan does **not** add well-scoping to those two — the active
   well narrows Explorer/Evidence display and narrows `:search`/`:trace`,
   exactly matching existing CLI semantics. `docs/tli.md` states this
   explicitly rather than the TUI silently pretending logs/config are
   well-scoped when they aren't.
3. **Active well is looked up by name everywhere in services**
   (`well_name: str`), but `TuiState.active_well_id` is spec'd as an id.
   Resolution: `TuiState` stores the active well's **name** (`active_well:
   str | None`), matching every service signature exactly, and the header/
   well-picker display the well's `purpose` and `member_count` alongside
   it. (Deviates from the literal dataclass in the pasted spec — noted
   here rather than silently diverging.)

No other service gaps were found: `list_artifacts`, `search`, `show`,
`trace`, `get_config_symbol`, `query_logs`, `run_doctor`, `add_note`,
`list_notes`, `create_well`, `add_member`, `show_well`, `list_all_wells`
already return typed Pydantic/dataclass results with full
`ProvenanceEnvelope`s, which is exactly the controller boundary this TUI
needs.

## State model

```python
# kairos/tui/state.py
@dataclass(frozen=True)
class Selection:
    kind: Literal["none", "artifact", "span", "entity", "relation",
                  "note", "well", "doctor_check"]
    id: str | None
    parent_id: str | None = None
    origin_view: str | None = None

@dataclass(frozen=True)
class ActivityEntry:
    id: str
    timestamp: datetime
    command: str
    mode: str
    status: Literal["success", "error", "cancelled"]
    summary: str
    result_reference: str | None

@dataclass(frozen=True)
class TuiState:
    workspace_path: Path
    mode: Literal["home", "artifacts", "search", "show", "trace", "well",
                  "config", "logs", "doctor", "history", "help"]
    active_well: str | None
    selection: Selection
    activity: tuple[ActivityEntry, ...]
    history_cursor: int | None
    status: Literal["idle", "loading", "error"]
    status_message: str | None
    # holds the last typed result set so panes can render without
    # re-querying: one Optional field per mode-shaped payload
    last_result: object | None
```

`TuiState` is immutable; the controller produces a new `TuiState` per
command and the app's reactive `state` attribute is reassigned wholesale.
No widget mutates `TuiState` fields directly.

## Controller / service boundary

```
CommandLine widget (user types ":search provenance")
      -> commands.parse(text) -> Command(name="search", args=["provenance"])
      -> controller.dispatch(ctx, state, command)     [may run in a worker]
      -> kairos.services.search.search(runtime_ctx, ...)
      -> new TuiState (+ ActivityEntry appended)
      -> app.state = new_state
      -> panes re-render from app.state via `watch_state`
```

`controller.py` holds one `dispatch(state, command) -> TuiState` function
per command name, each calling exactly one existing service function and
translating its typed result (or a `KairosError`) into a new `TuiState`.
The controller is plain Python with no Textual import, so it is unit
tested directly (no Pilot needed for controller-level tests).

## Command parser design

A command is `:<name> [args...]`, whitespace-split with one exception
(`:note add <id> <text with spaces>` takes the remainder as one string).
Aliases (`:s`, `:t`, `:q`, `?`, `/`) are resolved to their canonical name
before dispatch. Unknown commands produce a `CommandError` with a message
naming the closest valid command list — never a traceback. `:help` and
bare `?` share one path.

## Layouts

- **>=120 cols:** Explorer | Workspace | Evidence, three fixed-ratio
  columns, command line + status line pinned to the bottom.
- **80-119 cols:** Explorer | Workspace two columns; Evidence becomes a
  toggled overlay (`Tab`-reachable, same content, full detail, no
  truncation — it takes the screen instead of losing width).
- **<80 cols:** single primary pane (Workspace) plus Explorer/Evidence
  reachable as full-screen navigable views. Citations always render
  wrapped, never truncated mid-ID.

Implemented with Textual's reactive `size` watching in `app.py`
(`on_resize`) toggling a `layout_mode` reactive that screens read; this
avoids CSS-only breakpoint hacks that Textual doesn't natively support
and keeps the boundary testable via `pilot.resize`.

## Async / responsiveness

Every service call that touches the DB runs in a Textual `work()` worker.
A monotonically increasing `request_id` is stamped per dispatch; when a
worker's result arrives, the app discards it if `request_id` is stale
(superseded by a newer command) rather than racing the UI. Loading state
is a plain `status: "loading"` in `TuiState`, rendered as a short
status-line message — no spinner theatrics.

## Read-only enforcement

The controller only ever calls: `list_artifacts`, `search`, `show`,
`trace`, `get_config_symbol`, `query_logs`, `run_doctor`, `list_notes`,
`add_note`, `list_all_wells`, `show_well`, `create_well` (only from the
well-picker's explicit "create" affordance, if included — **not** included
in this alpha; well creation stays CLI-only), and `add_member` (**not**
included either — the well picker in this alpha only **activates/clears**
an existing well, per the spec's well-picker section, which lists no
"create" or "add" action). This keeps the alpha's mutation surface to
exactly `note add`, matching "The TUI is read-only toward registered
source artifacts."

## Test strategy

`tests/tui/` (new), using `textual.testing` / `App.run_test()` with an
explicit `size=` to avoid non-TTY width blowout, against `tmp_path`
workspaces built the same way `tests/integration/conftest.py` already
does (ingest the existing `tests/fixtures/*`). Split:

- `tests/tui/test_optional_dependency.py` — importability without
  Textual; requires a way to simulate "Textual absent" (monkeypatch
  `sys.modules["textual"] = None` and re-import the command module, or
  structure `commands/tui.py` so the import is checked via
  `importlib.util.find_spec` first, which is testable without breaking
  every other test's Textual import). Chosen approach: `find_spec` guard.
- `tests/tui/test_controller.py` — pure Python, no Pilot: dispatch each
  command against a real `RuntimeContext.open()` on an ingested tmp
  workspace, assert on the resulting `TuiState`.
- `tests/tui/test_app.py` — Pilot-driven: header content, pane focus
  cycling, `:search`/`:trace`/`:show`/`:config`/`:logs`/`:doctor`/`:well`
  rendering, error-path message (no traceback), history overlay, help
  overlay, resize behavior at 3 widths.

This covers the 23 required-test list from the spec by folding several
into shared parametrized tests rather than 23 separate files.

## CI strategy

Implemented: two new steps in `.github/workflows/ci.yml`'s existing
`test` job, placed immediately after the existing `pytest -q` step —
`pip install -e ".[tui,tui-test]"` (the job's earlier `Install` step
already installed `.[dev]`) then `pytest -q tests/tui`. Added as separate
steps rather than merged into the existing `Install`/`Pytest` steps so a
TUI-only flake doesn't mask a core-substrate failure, and so the base
`.[dev]`-only install path keeps being exercised exactly as it is today
(confirmed locally: `tests/tui/test_app.py` cleanly skips under `.[dev]`
alone rather than failing or silently no-op-passing).

## Non-goals (explicit)

No LLM, no chat, no NL planning, no embeddings/vector/fuzzy similarity, no
network, no telemetry, no API keys, no autonomous execution, no
background watchers, no shell execution, no source-file editing/mutation,
no multi-agent behavior, no device/remote-node integration, no web UI/
HTTP/WebSocket server, no graph visualization, no non-terminal GUI, no
`doctor` repair action, no reindex/ingest-from-the-TUI, no well
create/add-member from the TUI (CLI-only in this alpha, see above), no
command-palette natural-language input.
