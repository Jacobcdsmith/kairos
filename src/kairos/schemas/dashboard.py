"""Dashboard result — aggregate workspace stats rendered as the TUI home view."""

from __future__ import annotations

from pydantic import BaseModel

from kairos.schemas.activity import ActivityEvent


class DashboardMetric(BaseModel):
    """A single dashboard metric with count, label, and optional secondary info."""

    label: str
    value: str | int
    detail: str = ""


class ParseBreakdown(BaseModel):
    kind: str
    count: int
    status_ok: int
    status_error: int


class DashboardResult(BaseModel):
    """Aggregate workspace stats returned by :home."""

    # Totals
    total_artifacts: int = 0
    total_entities: int = 0
    total_relations: int = 0
    total_spans: int = 0
    total_wells: int = 0

    # Breakdowns
    artifacts_by_kind: list[ParseBreakdown] = []
    parse_errors: int = 0

    # Recent activity (last 5 events)
    recent_activity: list[ActivityEvent] = []

    # Workspace
    workspace_name: str = ""
