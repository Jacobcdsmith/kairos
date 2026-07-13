"""``kairos init`` service: create the workspace, run migrations, record the founding event."""

from __future__ import annotations

from pathlib import Path

from kairos.infrastructure.database.engine import session_scope
from kairos.services.context import RuntimeContext
from kairos.services.events import append_event


def init(root: Path, *, name: str | None = None) -> RuntimeContext:
    ctx = RuntimeContext.create(root, name=name)
    with session_scope(ctx.session_factory) as session:
        append_event(
            session,
            ctx.workspace,
            "workspace.init",
            {"root": str(ctx.workspace.root), "name": name or ctx.workspace.root.name},
        )
    return ctx
