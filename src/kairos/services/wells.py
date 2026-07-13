"""``kairos well create|add|remove|show|list`` — owner-curated working sets."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from kairos.domain.errors import (
    WellAlreadyExistsError,
    WellMemberNotFoundError,
    WellNotFoundError,
)
from kairos.domain.ids import new_id
from kairos.infrastructure.database.engine import session_scope
from kairos.infrastructure.database.orm import CoherenceWellRow, WellMemberRow
from kairos.infrastructure.database.repositories import (
    delete_well_member,
    get_well_by_name,
    get_well_member_by_id,
    insert_well,
    insert_well_member,
    list_well_members,
    list_wells,
)
from kairos.schemas.well import WellDetail, WellMemberResult, WellSummary
from kairos.services.context import RuntimeContext
from kairos.services.events import append_event
from kairos.services.target_resolution import resolve_target_kind


def _well_summary(row: CoherenceWellRow, member_count: int) -> WellSummary:
    return WellSummary(
        id=row.id,
        name=row.name,
        purpose=row.purpose,
        created_at=row.created_at,
        member_count=member_count,
    )


def create_well(ctx: RuntimeContext, name: str, purpose: str) -> WellSummary:
    with session_scope(ctx.session_factory) as session:
        if get_well_by_name(session, name) is not None:
            raise WellAlreadyExistsError(f"A coherence well named {name!r} already exists.")
        row = CoherenceWellRow(
            id=new_id(), name=name, purpose=purpose, created_at=datetime.now(UTC), metadata_json={}
        )
        insert_well(session, row)
        append_event(session, ctx.workspace, "well.create", {"well_id": row.id, "name": name})
        return _well_summary(row, 0)


def add_member(
    ctx: RuntimeContext, well_name: str, target_id: str, *, note: str | None = None
) -> WellMemberResult:
    with session_scope(ctx.session_factory) as session:
        well_row = get_well_by_name(session, well_name)
        if well_row is None:
            raise WellNotFoundError(f"No coherence well named: {well_name}")
        target_kind = resolve_target_kind(session, target_id)

        existing = _find_member(session, well_row.id, target_id)
        if existing is not None:
            return _member_result(existing)

        row = WellMemberRow(
            id=new_id(),
            well_id=well_row.id,
            target_id=target_id,
            target_kind=target_kind,
            added_at=datetime.now(UTC),
            note=note,
            metadata_json={},
        )
        insert_well_member(session, row)
        append_event(
            session,
            ctx.workspace,
            "well.add",
            {"well_id": well_row.id, "target_id": target_id},
        )
        return _member_result(row)


def _find_member(session: Session, well_id: str, target_id: str) -> WellMemberRow | None:
    for member in list_well_members(session, well_id):
        if member.target_id == target_id:
            return member
    return None


def remove_member(ctx: RuntimeContext, well_name: str, member_id: str) -> None:
    with session_scope(ctx.session_factory) as session:
        well_row = get_well_by_name(session, well_name)
        if well_row is None:
            raise WellNotFoundError(f"No coherence well named: {well_name}")
        member_row = get_well_member_by_id(session, member_id)
        if member_row is None or member_row.well_id != well_row.id:
            raise WellMemberNotFoundError(
                f"No member {member_id!r} in coherence well {well_name!r}"
            )
        delete_well_member(session, member_row)
        append_event(
            session,
            ctx.workspace,
            "well.remove",
            {"well_id": well_row.id, "member_id": member_id},
        )


def show_well(ctx: RuntimeContext, well_name: str) -> WellDetail:
    with session_scope(ctx.session_factory) as session:
        well_row = get_well_by_name(session, well_name)
        if well_row is None:
            raise WellNotFoundError(f"No coherence well named: {well_name}")
        members = list_well_members(session, well_row.id)
        return WellDetail(
            well=_well_summary(well_row, len(members)),
            members=[_member_result(m) for m in members],
        )


def list_all_wells(ctx: RuntimeContext) -> list[WellSummary]:
    with session_scope(ctx.session_factory) as session:
        rows = list_wells(session)
        return [_well_summary(row, len(list_well_members(session, row.id))) for row in rows]


def _member_result(row: WellMemberRow) -> WellMemberResult:
    return WellMemberResult(
        id=row.id,
        well_id=row.well_id,
        target_id=row.target_id,
        target_kind=row.target_kind,
        added_at=row.added_at,
        note=row.note,
    )
