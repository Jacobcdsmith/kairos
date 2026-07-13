"""Shared ``--well`` scoping: resolve a well name to the artifact ids it covers.

Used by both ``search`` and ``trace`` so the two commands' ``--well`` filter
means exactly the same thing.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from kairos.domain.errors import WellNotFoundError
from kairos.infrastructure.database.repositories import (
    get_span,
    get_well_by_name,
    list_well_members,
)


def well_artifact_ids(session: Session, well_name: str) -> list[str]:
    well_row = get_well_by_name(session, well_name)
    if well_row is None:
        raise WellNotFoundError(f"No coherence well named: {well_name}")
    artifact_ids: set[str] = set()
    for member in list_well_members(session, well_row.id):
        if member.target_kind == "artifact":
            artifact_ids.add(member.target_id)
        elif member.target_kind == "span":
            span_row = get_span(session, member.target_id)
            if span_row is not None:
                artifact_ids.add(span_row.artifact_id)
    return sorted(artifact_ids)
