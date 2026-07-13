# Contributing to KAIROS

Thanks for considering a contribution. KAIROS is a small, opinionated tool
with a narrow, deliberately-scoped mission — read the two sections below
before writing code, since they'll save you from work that can't be merged.

## Scope boundary (read this first)

KAIROS v0.1 explicitly does **not** implement, and will not accept PRs
implementing: hardware/embedded systems, device clients, simulations or
virtual companions, remote node management, external messaging
integrations, cloud services, multi-agent orchestration, autonomous
background execution, self-modification, or model inference / model-provider
integration. This isn't a "not yet" — it's a boundary the project is
designed around (see
[docs/architecture.md#non-goals-v01](docs/architecture.md#non-goals-v01)).
If your idea touches any of these, it belongs in a different project, or in
a GitHub Discussion first so we can talk about whether it fits at all.

Also non-negotiable, regardless of how a PR is framed:

- **Local-only.** No network calls, no telemetry, no cloud dependency —
  ever, not even optional.
- **Read-only with respect to registered sources.** KAIROS may add notes or
  well membership; it must never modify, move, or overwrite an ingested
  source file.
- **Nothing masquerades as source truth.** Raw bytes, parser-derived
  structure, and owner-authored notes are distinct provenance layers and
  must stay labeled as such in any new code path.
- **Every result carries its provenance**: artifact id, workspace-relative
  path, kind, an exact locator, parser version, and its raw/extracted/
  derived/user layer. If you add a new command or result type, wire it
  through `kairos.schemas.provenance.ProvenanceEnvelope`, don't invent a
  parallel shape.

## Development setup

Requires Python 3.12+.

```bash
git clone https://github.com/Jacobcdsmith/kairos.git
cd kairos
python -m venv .venv
.venv\Scripts\activate   # or: source .venv/bin/activate
pip install -e ".[dev]"
```

Run the full quality gate before opening a PR — this is exactly what CI runs:

```bash
ruff format --check src tests
ruff check src tests
pyright
pytest -q
```

`scripts/demo.sh` is a scripted walkthrough of every CLI command against the
fixtures in `tests/fixtures/`; run it if you've touched CLI output or a
parser.

## Architecture rules

The layering in `src/kairos/` is enforced by
`tests/unit/test_architecture_boundaries.py`, which fails CI if the domain
package ever imports Typer, Rich, SQLAlchemy, Alembic, pypdf, or any
infrastructure/cli/services/schemas module. Please still respect the
intent, not just the letter of what that one check covers:

- **`domain/`** — pure Python. Zero imports from Typer, Rich, SQLAlchemy, or
  any parser library. This is where `Artifact`, `SourceSpan`, `Locator`,
  and the `Parser` protocol live.
- **`infrastructure/`** — SQLAlchemy models and migrations, the six
  parsers, the content store, git metadata reading. Talks to the outside
  world; nothing here should encode business logic beyond "how do I read
  this format" or "how do I persist this row."
- **`schemas/`** — Pydantic v2 models at process boundaries (CLI
  input/output). Never used internally by `domain/` or `services/`.
- **`services/`** — application logic: ingest orchestration, entity
  reconciliation, search, trace, well/note management. This is where
  `infrastructure/` and `domain/` meet.
- **`cli/`** — Typer commands. Thin: parse args, call a service, render
  with Rich. No business logic here.

### Adding a parser

Every parser implements `kairos.domain.parser.Parser` (`kind`,
`parser_name`, `parser_version`, `sniff`, `parse`) and must:

- Never raise on malformed input — downgrade `parse_status` to `partial` or
  `failed` and record a `Diagnostic` instead. Nothing is silently dropped.
- Emit locators exact to the source type (add a new `LocatorKind` variant in
  `domain/locators.py` if the existing six don't fit — don't reuse
  `line_range` for something that isn't line-addressed).
- Emit at least one derived relation kind, so `kairos trace` has edges to
  walk through your new source kind, not just isolated spans.
- Ship both a well-formed and a deliberately malformed fixture under
  `tests/fixtures/`, and a unit test asserting the diagnostic path.

### Adding a CLI command

- Wrap the command body with `@cli_command` (`kairos.cli.errors`) so
  `KairosError` subclasses become a clean non-zero exit with a message on
  stderr, not a traceback.
- Escape any raw ingested text or paths with `rich.markup.escape()` before
  printing — source content can legitimately contain `[...]`, which Rich
  would otherwise interpret as markup.
- Add an integration test using `typer.testing.CliRunner` (see
  `tests/integration/conftest.py`), and update `docs/cli.md`.

## Commit and PR process

- Keep commits scoped to one logical change; the project history uses
  Conventional-Commits-style prefixes (`feat:`, `fix:`, `docs:`, `test:`,
  `chore:`) — not required, but appreciated.
- Open a PR against `main` and fill in the template's checklist. CI runs
  `ruff format --check`, `ruff check`, `pyright`, and `pytest` on every PR —
  all four must be green.
- For anything larger than a small fix (a new parser, a new command, a
  schema change), open an issue or Discussion first. Schema and CLI-contract
  changes especially benefit from discussion before code, since
  `docs/v0.1-status.md` documents what's currently a "stable contract."

## Reporting bugs and requesting features

Use the issue templates — they ask for exactly what's needed to reproduce
(exact commands, `kairos doctor` output, version). For anything that might
be a security issue (crash/RCE on crafted input, SQL injection, a write
outside `.kairos/`), see [SECURITY.md](SECURITY.md) instead of filing a
public issue.
