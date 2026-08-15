"""Event recording: every command appends a typed, append-only event record
to both the ``events`` table and ``.kairos/events.jsonl`` (the reproducible,
SQLite-independent mirror).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import event
from sqlalchemy.orm import Session

from kairos.domain.ids import new_id
from kairos.infrastructure.database.orm import EventRow
from kairos.infrastructure.database.repositories import insert_event
from kairos.infrastructure.filesystem.workspace import Workspace


def append_event(
    session: Session,
    workspace: Workspace,
    event_type: str,
    payload: dict[str, object],
) -> str:
    event_id = new_id()
    occurred_at = datetime.now(UTC)
    insert_event(
        session,
        EventRow(
            id=event_id,
            occurred_at=occurred_at,
            event_type=event_type,
            payload_json=payload,
        ),
    )
    session.flush()

    # The JSONL line is written *only after* the DB commit has succeeded.
    # Callers that use session_scope must therefore call append_event and then
    # let session_scope commit; we register a post-commit hook via SQLAlchemy's
    # after_commit event so that the file write is never attempted if the
    # transaction is rolled back.
    line = json.dumps(
        {
            "id": event_id,
            "occurred_at": occurred_at.isoformat(),
            "event_type": event_type,
            "payload": payload,
        },
        default=str,
    )
    events_path = workspace.events_path

    @event.listens_for(session, "after_commit", once=True)
    def _write_jsonl(
        _session: Session,
    ) -> None:  # pyright: ignore[reportUnusedFunction]
        try:
            with events_path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            # The DB commit already succeeded — the event is durable in SQLite.
            # A best-effort JSONL mirror failure should not crash the caller.
            pass

    return event_id
