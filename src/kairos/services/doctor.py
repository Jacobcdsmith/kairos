"""``kairos doctor`` — environment and workspace health checks.

The FTS5 check is the one that matters most: a Python build without FTS5
compiled into its bundled sqlite3 would otherwise fail silently on the first
``ingest`` or ``search``, deep inside a trigger, with a confusing error.
``content_integrity`` and ``fts_consistency`` catch a different class of
problem: the guarantees KAIROS makes (raw bytes never mutated, the search
index never drifts from ``source_spans``) are enforced by construction, not
by anything that would notice out-of-band interference (manual DB surgery,
bit rot, a future migration that forgets a trigger). ``doctor`` is where
that gets checked from the outside.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from sqlalchemy import text

from kairos.infrastructure.database.engine import fts5_is_available, session_scope
from kairos.infrastructure.database.repositories import list_artifacts
from kairos.schemas.doctor import DoctorCheck, DoctorReport
from kairos.services.context import RuntimeContext

_HASH_CHUNK_SIZE = 1024 * 1024


def _rehash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(_HASH_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    checks.append(_content_integrity_check(ctx))
    checks.append(_fts_consistency_check(ctx))

    return DoctorReport(checks=checks)


def _content_integrity_check(ctx: RuntimeContext) -> DoctorCheck:
    """Recompute every stored blob's hash and compare it to its artifact row.

    Catches bit rot or an out-of-band edit to ``.kairos/content/`` that
    ``ContentStore``'s write-once/chmod-read-only discipline is meant to
    prevent, but can't detect on its own from inside a single ``put()`` call.
    """
    with session_scope(ctx.session_factory) as session:
        artifact_rows = list_artifacts(session, limit=1_000_000)
        seen_sha256: set[str] = set()
        mismatched: list[str] = []
        missing: list[str] = []
        for row in artifact_rows:
            if row.sha256 in seen_sha256:
                continue
            seen_sha256.add(row.sha256)
            blob_path = ctx.content_store.path_for(row.sha256)
            if not blob_path.is_file():
                missing.append(row.id)
                continue
            if _rehash(blob_path) != row.sha256:
                mismatched.append(row.id)

    if not mismatched and not missing:
        return DoctorCheck(
            name="content_integrity",
            ok=True,
            detail=f"{len(seen_sha256)} stored blob(s) verified against their recorded sha256.",
        )
    detail_parts: list[str] = []
    if mismatched:
        detail_parts.append(f"hash mismatch for artifact(s): {', '.join(mismatched)}")
    if missing:
        detail_parts.append(f"missing blob for artifact(s): {', '.join(missing)}")
    return DoctorCheck(name="content_integrity", ok=False, detail="; ".join(detail_parts))


def _fts_consistency_check(ctx: RuntimeContext) -> DoctorCheck:
    """Confirm ``source_spans_fts`` and ``source_spans`` agree.

    The sync triggers created in the initial migration are supposed to make
    this impossible to violate through normal use; this check is what would
    notice if something bypassed them (direct SQL, a future migration that
    forgets a trigger).
    """
    with session_scope(ctx.session_factory) as session:
        span_count = session.execute(text("SELECT COUNT(*) FROM source_spans")).scalar_one()
        fts_count = session.execute(text("SELECT COUNT(*) FROM source_spans_fts")).scalar_one()
        orphan_count = session.execute(
            text(
                """
                SELECT COUNT(*) FROM source_spans_fts AS fts
                LEFT JOIN source_spans AS s ON s.id = fts.span_id
                WHERE s.id IS NULL
                """
            )
        ).scalar_one()

    ok = span_count == fts_count and orphan_count == 0
    detail = (
        f"source_spans={span_count}, source_spans_fts={fts_count}, orphaned_fts_rows={orphan_count}"
    )
    return DoctorCheck(name="fts_consistency", ok=ok, detail=detail)
