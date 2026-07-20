# KAIROS Agent Attachment Protocol

> **What this file is:** instructions for any AI coding agent (Cline, Claude Code, Codex, Copilot, Hermes, etc.) on how to connect to and use a KAIROS workspace. Load this at session start when working in a repo that contains a `.kairos/` directory or `kairos.toml`.

## 1. Detect

A KAIROS workspace is present if either of these exists at the project root:

```
.kairos/              # workspace database and config
kairos.toml           # workspace configuration file
```

If neither exists, ask the user if they want to initialize one:

```bash
pip install kairos
kairos init .
kairos ingest . --recursive
```

## 2. Connect

The `kairos` package is installed as a project dependency. Connect through the agent tool adapter:

```python
from kairos.tool import (
    kairos_status,      # workspace aggregate stats
    kairos_search,      # FTS5 full-text search → ranked hits
    kairos_trace,       # bidirectional BFS entity trace
    kairos_show,        # full artifact detail + spans
    kairos_ingest,      # ingest files into the workspace
)
```

Each function returns `{"status": "ok", …}` or `{"status": "error", "error": "…"}` — never raises.

## 3. Workflow

Use this pattern when answering questions or making changes that touch unfamiliar code:

```
auto-ingest  →  well  →  search  →  show / trace  →  source-link
```

### Step-by-step

**1. Auto-ingest** — ensure the workspace reflects the current file tree:

```python
kairos_ingest(src_path, recursive=True)
```

The ingest is idempotent: already-known files are silently skipped. Run this at session start for the directories you'll be touching.

**2. Scope with a well (optional)** — a "well" is a named query scope. Search and trace automatically filter to well members:

```python
kairos_well_create("my-task", "files touched by this task")
# then add artifacts or spans:
kairos_well_add_member("my-task", "<id>")
# activate:
kairos_well_use("my-task")
```

**3. Search** — FTS5 full-text search returns ranked hits with exact locators:

```python
hits = kairos_search("database engine OR session factory", well="my-task")
```

Each hit includes:
- `provenance.locator_str` — the `file://#L,C` form
- `provenance.source_path` — relative workspace path
- `source_link` — clickable `vscode://file/…` URL
- `span_id` — to drill into with `kairos_show`

**4. Show / Trace** — drill into artifacts or follow relations:

```python
# full artifact detail with all spans:
detail = kairos_show("<artifact-id>")

# BFS trace across entities/relations:
trace = kairos_trace("SymbolType", depth=2)
```

**5. Read source content** — resolved locators point at actual file bytes:

```python
content = kairos_source_content("<span-id>", ctx_lines=3)
```

Returns the source excerpt around the locator. Use this instead of reading the whole file.

## 4. Source Links

Every search hit and trace node carries a `source_link` field:

```
source_link: file:///C:/Users/you/project/src/module.py#104,224
             vscode://file/C:/Users/you/project/src/module.py:104
```

Both forms are clickable in most terminals. The numbers are `start_line,end_line` from the parser locator.

## 5. Hermes Agent Integration

If running inside **Hermes Agent**, the `kairos-agent-tool` skill auto-loads the import pattern. Load it at session start:

```
Load skill: kairos-agent-tool
```

The skill provides:
- The exact import incantation
- Pitfalls for each command
- The auto-ingest → well → search → trace → source-link workflow

## 6. Multiple Workspaces

A KAIROS workspace is per-project. Each project root with `kairos init` gets its own `.kairos/` directory. The tool adapter auto-detects the nearest workspace by walking up the directory tree. To use a different workspace, pass the path explicitly:

```python
from kairos.tool import kairos_init
kairos_init(path="/other/project")
```

---

**TL;DR:** `pip install kairos`, `kairos init .`, `kairos ingest . --recursive`, then `from kairos.tool import kairos_search`.
