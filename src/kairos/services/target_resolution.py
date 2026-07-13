"""Shared target-kind resolution: a note or well member can point at either
an artifact or a source span, and every caller needs to classify which.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from kairos.domain.errors import TargetNotFoundError
from kairos.infrastructure.database.repositories import get_artifact, get_span


def resolve_target_kind(session: Session, target_id: str) -> str:
    if get_artifact(session, target_id) is not None:
        return "artifact"
    if get_span(session, target_id) is not None:
        return "span"
    raise TargetNotFoundError(f"No artifact or span with id: {target_id}")
