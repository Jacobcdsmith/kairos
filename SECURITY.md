# Security Policy

## Scope

KAIROS is a local-first CLI: it makes no network calls, runs no background
services, and every write is confined to a workspace's `.kairos/` directory
(see [docs/architecture.md](docs/architecture.md)). The realistic attack
surface is narrow but not zero — it still parses untrusted file content
(Markdown, PDF, JSON, Kconfig-menu JSON, logs, Python source) and executes
raw SQL against a local SQLite database. Reports in scope include:

- A crafted input file (any of the six supported source kinds) that causes
  a crash, hang, unbounded resource use, or arbitrary code execution during
  `kairos ingest`.
- SQL injection through `kairos search`/`kairos logs` query strings, or
  through any value derived from ingested content that reaches a SQL
  statement without parameterization.
- Path traversal or symlink handling in the content store
  (`kairos.infrastructure.filesystem.content_store`) that could write
  outside `.kairos/content/`.
- Any write to a registered source path — KAIROS's read-only guarantee is a
  core contract, not just a preference.

## Out of scope

- Denial of service via arbitrarily large inputs you choose to ingest
  yourself — you control what you feed `kairos ingest`.
- Issues that require local code execution privileges beyond what running
  the CLI already grants (KAIROS has no privilege boundary to cross; it runs
  as the invoking user, same as any local script).

## Reporting a Vulnerability

Please do not open a public issue for a suspected vulnerability. Instead,
email **jacobcsmithd@gmail.com** with:

- A description of the issue and its impact.
- Steps to reproduce, ideally with a minimal synthetic input file (not real
  personal data).
- The KAIROS version or commit hash.

You should expect an initial response within 5 business days. Once a fix is
available, it will ship as a patch release with credit to the reporter
(unless you'd prefer otherwise).
