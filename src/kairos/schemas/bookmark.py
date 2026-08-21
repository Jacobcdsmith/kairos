"""Result schema for TUI bookmarks — named, saved commands for quick recall."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BookmarkResult(BaseModel):
    name: str
    command: str
    created_at: datetime
