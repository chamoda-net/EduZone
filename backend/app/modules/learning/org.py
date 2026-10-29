"""Organization console side of learning: who is in a class and who has access, manual
access (scholarships, free access), and the inbox of requests for past months.
Same permission rule as the catalogue: owners/admins everything, teachers their classes."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.errors import ApiError
from app.modules.auth.dependencies import Actor
from app.modules.catalog.service import load_class
from app.modules.learning import access
from app.modules.learning import repository as repo
from app.modules.learning.schemas import (
    ClassStudent,
    GrantCreate,
    GrantInfo,
    LateRequestDecision,
    LateRequestRow,
)


async def _audit(session: AsyncSession, actor: Actor, action: str, entity_type: str, entity_id: UUID,
                 details: dict[str, object]) -> None:
    await write_audit(session, actor_user_id=actor.auth.user_id, action=action, entity_type=entity_type,
                      entity_id=entity_id, details=details, ip=actor.ip)


async def class_students(session: AsyncSession, actor: Actor, class_id: UUID,
                         month_id: UUID | None) -> list[ClassStudent]:
    c = await load_class(session, actor, class_id)
    month_match = "g.class_month_id = :mo" if month_id else "g.class_month_id IS NULL"
    rows = (await session.execute(text(f"""
        WITH people AS (
            SELECT student_member_id FROM class_enrollments WHERE class_id = :c
            UNION
            SELECT student_member_id FROM access_grants WHERE class_id = :c
        )
        SELECT tm.id AS member_id, u.full_name, u.phone, e.status AS enrollment_status, e.enrolled_at,
               g.id AS grant_id, g.source, g.granted_at
        FROM people p
        JOIN tenant_members tm ON tm.id = p.student_member_id
        JOIN users u ON u.id = tm.user_id
        LEFT JOIN class_enrollments e ON e.class_id = :c AND e.student_member_id = tm.id
        LEFT JOIN access_grants g ON g.student_member_id = tm.id AND g.class_id = :c AND {month_match}
                                  AND {access.ACTIVE_GRANT}
        ORDER BY (e.status = 'active') DESC NULLS LAST, u.full_name
    """), {"c": c.id, "mo": month_id})).all()
    return [
        ClassStudent(member_id=r.member_id, full_name=r.full_name, phone=r.phone,
                     enrollment_status=r.enrollment_status, enrolled_at=r.enrolled_at,
                     access=GrantInfo(id=r.grant_id, source=r.source, granted_at=r.granted_at) if r.grant_id else None)
        for r in rows
    ]


async def create_grant(session: AsyncSession, actor: Actor, class_id: UUID, body: GrantCreate) -> GrantInfo:
    c = await load_class(session, actor, class_id, for_update=True)
    student = (await session.execute(text("SELECT role, status FROM tenant_members WHERE id = :m"),
                                     {"m": body.student_member_id})).one_or_none()
    if student is None or student.role != "student" or student.status != "active":
        raise ApiError("STUDENT_INVALID", "Choose an active student of this organization.")
    if c.pricing_model == "monthly":
        if body.class_month_id is None:
            raise ApiError("MONTH_REQUIRED", "Choose the month to give access to.")
        month = await repo.month_with_class(session, body.class_month_id)
        if month is None or month.class_id != c.id:
            raise ApiError("MONTH_INVALID", "That month does not belong to this class.")
    elif body.class_month_id is not None:
        raise ApiError("MONTH_INVALID", "Only monthly classes give access per month.")
    if await access.active_grant_for(session, body.student_member_id, c.id, body.class_month_id) is not None:
        raise ApiError("ALREADY_HAS_ACCESS", "This student already has access.", status_code=409)

    await repo.upsert_enrollment(session, body.student_member_id, c.id)  # access implies membership
    grant_id = await repo.insert_grant(session, member_id=body.student_member_id, class_id=c.id,
                                       month_id=body.class_month_id, source=body.source,
                                       granted_by=actor.auth.member_id)
    await _audit(session, actor, "access_grant.create", "access_grant", grant_id,
                 {"student_member_id": body.student_member_id, "class_id": c.id,
                  "class_month_id": body.class_month_id, "source": body.source})
    g = (await session.execute(text("SELECT id, source, granted_at FROM access_grants WHERE id = :id"),
                               {"id": grant_id})).one()
    return GrantInfo(id=g.id, source=g.source, granted_at=g.granted_at)


async def revoke_grant(session: AsyncSession, actor: Actor, grant_id: UUID, reason: str | None) -> None:
    g = (await session.execute(text("""
        SELECT id, class_id, source, revoked_at FROM access_grants WHERE id = :id FOR UPDATE
    """), {"id": grant_id})).one_or_none()
    if g is None:
        raise ApiError("NOT_FOUND", "Access not found.", status_code=404)
    try:
        await load_class(session, actor, g.class_id)
    except ApiError:
        raise ApiError("NOT_FOUND", "Access not found.", status_code=404) from None
    if g.source == "purchase":
        # Paid access is withdrawn through a refund (step 7), which keeps the ledger right.
        raise ApiError("PURCHASE_GRANT", "Paid access can only be removed with a refund.", status_code=409)
    if g.revoked_at is not None:
        raise ApiError("ALREADY_REVOKED", "This access was already removed.", status_code=409)
    await session.execute(text("UPDATE access_grants SET revoked_at = now(), revoke_reason = :r WHERE id = :id"),
                          {"id": g.id, "r": reason})
    await _audit(session, actor, "access_grant.revoke", "access_grant", g.id, {"reason": reason})


_REQUEST_SELECT = """
    SELECT r.id, r.status, r.student_member_id, u.full_name AS student_name, u.phone AS student_phone,
           c.id AS class_id, c.title AS class_title, r.class_month_id, m.month_start,
           r.student_note, r.decision_note, r.created_at, r.decided_at, c.teacher_member_id
    FROM late_month_requests r
    JOIN class_months m ON m.id = r.class_month_id
    JOIN classes c ON c.id = m.class_id
    JOIN tenant_members tm ON tm.id = r.student_member_id
    JOIN users u ON u.id = tm.user_id
"""


def _request_row(r: Any) -> LateRequestRow:
    return LateRequestRow.model_validate({k: getattr(r, k) for k in LateRequestRow.model_fields})


async def late_requests(session: AsyncSession, actor: Actor, status: str) -> list[LateRequestRow]:
    rows = (await session.execute(text(f"""
        {_REQUEST_SELECT}
        WHERE r.status = :st AND (CAST(:teacher AS uuid) IS NULL OR c.teacher_member_id = :teacher)
        ORDER BY r.created_at {"ASC" if status == "pending" else "DESC"}
        LIMIT 200
    """), {"st": status, "teacher": None if actor.manages_all else actor.auth.member_id})).all()
    return [_request_row(r) for r in rows]


async def decide_late_request(session: AsyncSession, actor: Actor, request_id: UUID,
                              body: LateRequestDecision) -> LateRequestRow:
    r = (await session.execute(text(f"{_REQUEST_SELECT} WHERE r.id = :id FOR UPDATE OF r"),
                               {"id": request_id})).one_or_none()
    if r is None or not (actor.manages_all or r.teacher_member_id == actor.auth.member_id):
        raise ApiError("NOT_FOUND", "Request not found.", status_code=404)
    if r.status != "pending":
        raise ApiError("REQUEST_DECIDED", "This request was already answered.", status_code=409)
    status = "approved" if body.decision == "approve" else "rejected"
    await session.execute(text("""
        UPDATE late_month_requests
        SET status = :st, decided_by = :by, decided_at = now(), decision_note = :note
        WHERE id = :id
    """), {"st": status, "by": actor.auth.member_id, "note": body.note, "id": r.id})
    await _audit(session, actor, f"late_request.{body.decision}", "late_month_request", r.id,
                 {"student_member_id": r.student_member_id, "class_month_id": r.class_month_id})
    updated = (await session.execute(text(f"{_REQUEST_SELECT} WHERE r.id = :id"), {"id": r.id})).one()
    return _request_row(updated)
