"""``kairos doctor`` — environment and workspace health checks.

The FTS5 check is the one that matters most: a Python build without FTS5
compiled into its bundled sqlite3 would otherwise fail silently on the first
``ingest`` or ``search``, deep inside a trigger, with a confusing error.
"""

from __future__ import annotations

from sqlalchemy import text

from kairos.infrastructure.database.engine import fts5_is_available, session_scope
from kairos.schemas.doctor import DoctorCheck, DoctorReport
from kairos.services.context import RuntimeContext


def run_doctor(ctx: RuntimeContext) -> DoctorReport:
    checks: list[DoctorCheck] = []

    fts_ok = fts5_is_available()
    fts_detail = (
        "FTS5 is compiled into this Python's sqlite3."
        if fts_ok
        else "FTS5 is NOT available in this Python's sqlite3 build — search/ingest will fail."
    )
    checks.append(DoctorCheck(name="fts5_available", ok=fts_ok, detail=fts_detail))

    checks.append(
        DoctorCheck(
            name="workspace_root",
            ok=ctx.workspace.kairos_dir.is_dir(),
            detail=str(ctx.workspace.root),
        )
    )

    try:
        with session_scope(ctx.session_factory) as session:
            version = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        checks.append(
            DoctorCheck(
                name="schema_migration",
                ok=version == "0001",
                detail=f"alembic_version={version!r}",
            )
        )
    except Exception as exc:  # any DB failure here is itself the diagnostic being reported
        checks.append(
            DoctorCheck(name="schema_migration", ok=False, detail=f"Could not read schema: {exc}")
        )

    content_dir_ok = ctx.workspace.content_dir.is_dir()
    checks.append(
        DoctorCheck(
            name="content_store",
            ok=content_dir_ok,
            detail=str(ctx.workspace.content_dir),
        )
    )

    events_ok = ctx.workspace.events_path.is_file()
    checks.append(
        DoctorCheck(name="events_log", ok=events_ok, detail=str(ctx.workspace.events_path))
    )

    return DoctorReport(checks=checks)
