"""Result schemas for ``kairos note``."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NoteResult(BaseModel):
    id: str
    target_id: str
    target_kind: str
    body: str
    created_at: datetime
    supersedes_note_id: str | None
