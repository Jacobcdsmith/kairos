"""Event recording: every command appends a typed, append-only event record
to both the ``events`` table and ``.kairos/events.jsonl`` (the reproducible,
SQLite-independent mirror).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

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

    line = {
        "id": event_id,
        "occurred_at": occurred_at.isoformat(),
        "event_type": event_type,
        "payload": payload,
    }
    with workspace.events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, default=str) + "\n")

    return event_id
