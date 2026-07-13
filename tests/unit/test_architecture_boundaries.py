"""Enforce the architecture layering CONTRIBUTING.md and docs/architecture.md
promise: ``domain -> infrastructure -> services -> cli``, with the domain
package having zero dependency on Typer, Rich, SQLAlchemy, Alembic, pypdf,
or any of the other three layers. This was previously "enforced by
convention, not tooling" (CONTRIBUTING.md's own words) — this test is the
tooling. It runs as part of the normal ``pytest`` step already gated in
``.github/workflows/ci.yml``, so CI fails automatically if a future change
introduces a prohibited import, with no new linting framework required.
"""

from __future__ import annotations

import ast
from pathlib import Path

_DOMAIN_DIR = Path(__file__).parent.parent.parent / "src" / "kairos" / "domain"

_PROHIBITED_PREFIXES = (
    "typer",
    "rich",
    "sqlalchemy",
    "alembic",
    "pypdf",
    "kairos.infrastructure",
    "kairos.cli",
    "kairos.services",
    "kairos.schemas",
)


def _imported_module_names(source: str) -> list[str]:
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    return names


def test_domain_layer_has_no_prohibited_imports() -> None:
    domain_files = sorted(_DOMAIN_DIR.glob("*.py"))
    assert domain_files, f"expected to find domain module files under {_DOMAIN_DIR}"

    violations: list[str] = []
    for path in domain_files:
        for name in _imported_module_names(path.read_text(encoding="utf-8")):
            if any(
                name == prefix or name.startswith(prefix + ".") for prefix in _PROHIBITED_PREFIXES
            ):
                violations.append(f"{path.name} imports {name!r}")

    assert not violations, (
        "domain layer must not depend on infrastructure/cli/services/schemas:\n"
        + "\n".join(violations)
    )
