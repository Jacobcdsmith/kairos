"""Read-only access to the append-only event log — the TUI Explorer's
"recent local activity" list. ``kairos.services.events.append_event`` is the
only writer; this module never writes.
"""

from __future__ import annotations

from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.repositories import list_events
from kairos.schemas.activity import ActivityEvent
from kairos.services.context import RuntimeContext


def recent_events(ctx: RuntimeContext, *, limit: int = 20) -> list[ActivityEvent]:
    with session_scope(ctx.session_factory) as session:
        rows = list_events(session, limit=limit)
        return [
            ActivityEvent(
                id=row.id,
                occurred_at=row.occurred_at,
                event_type=row.event_type,
                payload=row.payload_json,
            )
            for row in rows
        ]
