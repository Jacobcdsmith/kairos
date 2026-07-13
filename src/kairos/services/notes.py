"""``kairos note add|list`` — owner-authored context, stored apart from source and extraction."""

from __future__ import annotations

from datetime import UTC, datetime

from kairos.domain.ids import new_id
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.orm import NoteRow
from kairos.infrastructure.database.repositories import insert_note, list_notes_for_target
from kairos.schemas.note import NoteResult
from kairos.services.context import RuntimeContext
from kairos.services.events import append_event
from kairos.services.target_resolution import resolve_target_kind


def add_note(ctx: RuntimeContext, target_id: str, text: str) -> NoteResult:
    with session_scope(ctx.session_factory) as session:
        target_kind = resolve_target_kind(session, target_id)
        note_id = new_id()
        created_at = datetime.now(UTC)
        row = NoteRow(
            id=note_id,
            target_id=target_id,
            target_kind=target_kind,
            body=text,
            created_at=created_at,
            supersedes_note_id=None,
            metadata_json={},
        )
        insert_note(session, row)
        append_event(
            session, ctx.workspace, "note.add", {"target_id": target_id, "note_id": note_id}
        )
        return NoteResult(
            id=row.id,
            target_id=row.target_id,
            target_kind=row.target_kind,
            body=row.body,
            created_at=row.created_at,
            supersedes_note_id=row.supersedes_note_id,
        )


def list_notes(ctx: RuntimeContext, target_id: str) -> list[NoteResult]:
    with session_scope(ctx.session_factory) as session:
        rows = list_notes_for_target(session, target_id)
        return [
            NoteResult(
                id=row.id,
                target_id=row.target_id,
                target_kind=row.target_kind,
                body=row.body,
                created_at=row.created_at,
                supersedes_note_id=row.supersedes_note_id,
            )
            for row in rows
        ]
