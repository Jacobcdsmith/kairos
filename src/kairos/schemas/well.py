"""Result schemas for ``kairos well``."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WellSummary(BaseModel):
    id: str
    name: str
    purpose: str
    created_at: datetime
    member_count: int


class WellMemberResult(BaseModel):
    id: str
    well_id: str
    target_id: str
    target_kind: str
    added_at: datetime
    note: str | None


class WellDetail(BaseModel):
    well: WellSummary
    members: list[WellMemberResult]
