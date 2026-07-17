"""Result schema for recent local activity (the TUI Explorer's "recent local
events" list). Thin read-side counterpart to ``kairos.services.events``,
which only ever appends.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ActivityEvent(BaseModel):
    id: str
    occurred_at: datetime
    event_type: str
    payload: dict[str, object]
