"""Explicit, immutable TUI state. Nothing here imports Textual — this module
is plain Python so ``controller.py`` can be unit tested without a Pilot.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal, cast

from kairos.schemas.activity import ActivityEvent
from kairos.schemas.artifact import ArtifactDetail, ArtifactSummary
from kairos.schemas.config import ConfigSymbolResult
from kairos.schemas.dashboard import DashboardResult
from kairos.schemas.doctor import DoctorReport
from kairos.schemas.logs import LogHit
from kairos.schemas.note import NoteResult
from kairos.schemas.search import SearchResult
from kairos.schemas.trace import TraceResult
from kairos.schemas.well import WellDetail, WellSummary

SelectionKind = Literal[
    "none",
    "artifact",
    "span",
    "entity",
    "relation",
    "note",
    "well",
    "doctor_check",
]

Mode = Literal[
    "home",
    "artifacts",
    "search",
    "show",
    "trace",
    "well",
    "config",
    "logs",
    "doctor",
    "history",
    "help",
    # Not in the spec's literal Mode list verbatim: `:note add`/`:note list`
    # needs its own shape (`list[NoteResult]`) distinct from `:show`'s
    # `ArtifactDetail`, so it gets its own mode rather than overloading
    # "show" with two incompatible `last_result` shapes. See
    # docs/tli-implementation-plan.md's service-layer-gaps section for the
    # other documented deviations from the pasted spec's literal dataclass.
    "notes",
]

FocusTarget = Literal["explorer", "workspace", "evidence", "command_line"]

# The one payload shape each mode's Workspace/Explorer pane renders from.
# Exactly one of these is populated in `TuiState.last_result` at a time,
# matching `TuiState.mode`.
ModeResult = (
    DashboardResult
    | SearchResult
    | TraceResult
    | ArtifactDetail
    | list[ArtifactSummary]
    | DoctorReport
    | list[LogHit]
    | ConfigSymbolResult
    | list[WellSummary]
    | WellDetail
    | list[NoteResult]
    | list[ActivityEvent]
    | None
)


@dataclass(frozen=True, slots=True)
class Selection:
    kind: SelectionKind = "none"
    id: str | None = None
    parent_id: str | None = None
    origin_view: str | None = None


@dataclass(frozen=True, slots=True)
class ActivityEntry:
    id: str
    timestamp: datetime
    command: str
    mode: str
    status: Literal["success", "error", "cancelled"]
    summary: str
    result_reference: str | None = None


@dataclass(frozen=True, slots=True)
class TuiState:
    workspace_path: Path
    mode: Mode = "home"
    # Looked up by name, not id — every well service function (`search`,
    # `trace`, `show_well`, `add_member`, ...) takes a well *name*. See
    # docs/tli-implementation-plan.md's service-layer-gaps section for why
    # this deviates from the spec's `active_well_id`.
    active_well: str | None = None
    selection: Selection = field(default_factory=Selection)
    activity: tuple[ActivityEntry, ...] = ()
    history_cursor: int | None = None
    status: Literal["idle", "loading", "error"] = "idle"
    status_message: str | None = None
    last_result: ModeResult = None
    focus: FocusTarget = "command_line"


def as_list_of[T](value: object, item_type: type[T]) -> list[T] | None:
    """Narrow ``TuiState.last_result`` (a big union) to ``list[item_type]``.

    Checking ``isinstance(value[0], item_type)`` alone tells pyright the
    *first element's* type, not the whole list's — every widget that reads
    ``last_result`` needs this same narrowing, so it lives here once rather
    than as a repeated `isinstance(result, list) and result and
    isinstance(result[0], ...)` + unchecked-union-access pattern in each of
    explorer_pane.py/workspace_pane.py/evidence_pane.py.
    """
    if isinstance(value, list) and value and isinstance(value[0], item_type):
        return cast("list[T]", value)
    return None
