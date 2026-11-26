"""Seat requests and the notify list (docs/SEATS.md), in the class's tenant transaction.

A class whose registration is `ask`: a new student asks for a seat (one row per student, class and month), the class's
teacher or an owner/admin accepts, which holds a seat for SEAT_REQUEST_HOLD_HOURS, or refuses. An accepted request whose
time passed is `expired` by itself; the student may ask again. A refused student may not ask again for the same month,
but staff can still accept them.

The notify list is for a class that can't be joined now (full or closed): one row per student and class, gone when they
get a seat. It sends nothing yet: the student area shows when a seat is open.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.errors import ApiError
from app.modules.auth.dependencies import Actor, AuthContext, ensure_student_member
from app.modules.checkout.service import require_verified_phone
from app.modules.learning import access
from app.modules.seats import service as seats
from app.modules.seats.schemas import MySeatRequest, SeatDecision, SeatRequestIn, SeatRequestRow, SeatWait

_BLOCKED = {"CLASS_FULL", "REGISTRATION_CLOSED"}


async def _open_class(session: AsyncSession, class_id: UUID) -> Any:
    c = (await session.execute(text("""
        SELECT id, title, pricing_model FROM classes WHERE id = :c AND kind = 'tuition' AND status = 'published'
    """), {"c": class_id})).one_or_none()
    if c is None:
        raise ApiError("NOT_FOUND", "Class not found.", status_code=404)
    return c


async def _check_month(session: AsyncSession, c: Any, month_id: UUID | None) -> None:
    if c.pricing_model != "monthly":
        if month_id is not None:
            raise ApiError("MONTH_INVALID", "This class has no months.")
        return
    if month_id is None:
        raise ApiError("MONTH_REQUIRED", "Choose the month.")
    status = (await session.execute(text("SELECT status FROM class_months WHERE id = :mo AND class_id = :c"),
                                    {"mo": month_id, "c": c.id})).scalar_one_or_none()
    if status is None:
        raise ApiError("MONTH_INVALID", "That month does not belong to this class.")
    if status != "open":
        raise ApiError("MONTH_NOT_OPEN", "This month isn't open.", status_code=409)


# --- the student ------------------------------------------------------------------------------------

async def ask(session: AsyncSession, auth: AuthContext, class_id: UUID, body: SeatRequestIn) -> MySeatRequest:
    c = await _open_class(session, class_id)
    await require_verified_phone(session, auth.user_id)
    await _check_month(session, c, body.class_month_id)
    auth = await ensure_student_member(session, auth)
    if (c.pricing_model != "free"                    # (an old free grant without a seat may still ask)
            and await access.active_grant_for(session, auth.member_id, c.id, body.class_month_id) is not None):
        raise ApiError("ALREADY_HAS_ACCESS", "You already have access.", status_code=409)
    r = (await session.execute(text(f"""
        SELECT {seats.REQUEST_STATUS} AS status FROM seat_requests r
        WHERE r.class_id = :c AND r.class_month_id IS NOT DISTINCT FROM CAST(:mo AS uuid) AND r.student_member_id = :m
        FOR UPDATE
    """), {"c": c.id, "mo": body.class_month_id, "m": auth.member_id})).one_or_none()
    if r is not None and r.status in ("pending", "approved"):
        raise ApiError("REQUEST_EXISTS", "You have already asked for a seat.", status_code=409)
    if r is not None and r.status == "rejected":
        raise ApiError("REQUEST_REJECTED", "The teacher already answered this request.", status_code=409)
    # Only when asking is what's needed.
    try:
        await seats.check(session, c.id, body.class_month_id, auth.member_id)
    except ApiError as exc:
        if exc.code != "SEAT_REQUEST_REQUIRED":
            raise
    else:
        raise ApiError("REQUEST_NOT_NEEDED", "You can join without asking.", status_code=409)
    request_id = (await session.execute(text("""
        INSERT INTO seat_requests (tenant_id, class_id, class_month_id, student_member_id, student_note)
        VALUES (current_tenant_id(), :c, :mo, :m, :note)
        ON CONFLICT (class_id, class_month_id, student_member_id) DO UPDATE
        SET status = 'pending', student_note = EXCLUDED.student_note, created_at = now(),
            decided_by = NULL, decided_at = NULL, decision_note = NULL, held_until = NULL
        RETURNING id
    """), {"c": c.id, "mo": body.class_month_id, "m": auth.member_id,
            "note": (body.note or "").strip() or None})).scalar_one()
    return next(x for x in await mine(session, auth.member_id) if x.id == request_id)


async def withdraw(session: AsyncSession, auth: AuthContext, class_id: UUID, month_id: UUID | None) -> None:
    done = (await session.execute(text("""
        UPDATE seat_requests SET status = 'withdrawn'
        WHERE class_id = :c AND class_month_id IS NOT DISTINCT FROM CAST(:mo AS uuid) AND student_member_id = :m
          AND status IN ('pending', 'approved') RETURNING id
    """), {"c": class_id, "mo": month_id, "m": auth.member_id})).first()
    if done is None:
        raise ApiError("NOT_FOUND", "You have no open request for this class.", status_code=404)


async def mine(session: AsyncSession, member_id: UUID | None) -> list[MySeatRequest]:
    rows = (await session.execute(text(f"""
        SELECT r.id, {seats.REQUEST_STATUS} AS status, r.held_until, r.decision_note, r.created_at, r.student_note,
               c.id AS class_id, c.title AS class_title, m.month_start
        FROM seat_requests r JOIN classes c ON c.id = r.class_id LEFT JOIN class_months m ON m.id = r.class_month_id
        WHERE r.student_member_id = :m AND r.status NOT IN ('withdrawn', 'used')
        ORDER BY r.created_at DESC LIMIT 100
    """), {"m": member_id})).all()
    return [MySeatRequest(**r._mapping) for r in rows]


# --- the notify list ----------------------------------------------------------------------------------

async def _problems(session: AsyncSession, c: Any, member_id: UUID | None) -> list[str | None]:
    """For everything of the class that is open and they haven't got: why they can't join now (None: they can)."""
    months: list[UUID | None] = [None]
    if c.pricing_model == "monthly":
        months = list((await session.execute(text(
            "SELECT id FROM class_months WHERE class_id = :c AND status = 'open' ORDER BY month_start"),
            {"c": c.id})).scalars())
    out: list[str | None] = []
    for mo in months:
        if member_id is not None and await access.active_grant_for(session, member_id, c.id, mo) is not None:
            continue
        out.append((await seats.state(session, c.id, mo, member_id)).problem)
    return out


async def wait(session: AsyncSession, auth: AuthContext, class_id: UUID) -> None:
    c = await _open_class(session, class_id)
    auth = await ensure_student_member(session, auth)
    problems = await _problems(session, c, auth.member_id)
    if not problems or any(p not in _BLOCKED for p in problems):
        raise ApiError("WAIT_NOT_NEEDED", "You don't need to wait: you're in, or you can join now.", status_code=409)
    await session.execute(text("""
        INSERT INTO seat_waits (tenant_id, class_id, student_member_id) VALUES (current_tenant_id(), :c, :m)
        ON CONFLICT (class_id, student_member_id) DO NOTHING
    """), {"c": c.id, "m": auth.member_id})


async def stop_waiting(session: AsyncSession, auth: AuthContext, class_id: UUID) -> None:
    await session.execute(text("DELETE FROM seat_waits WHERE class_id = :c AND student_member_id = :m"),
                          {"c": class_id, "m": auth.member_id})


async def my_waits(session: AsyncSession, member_id: UUID) -> list[SeatWait]:
    rows = (await session.execute(text("""
        SELECT c.id, c.title, c.pricing_model, w.created_at FROM seat_waits w
        JOIN classes c ON c.id = w.class_id AND c.status = 'published'
        WHERE w.student_member_id = :m ORDER BY w.created_at DESC LIMIT 100
    """), {"m": member_id})).all()
    out = []
    for c in rows:
        ready = [p for p in await _problems(session, c, member_id) if p not in _BLOCKED]
        out.append(SeatWait(class_id=c.id, class_title=c.title, created_at=c.created_at, available=bool(ready),
                            needs_request=bool(ready) and None not in ready))
    return out


# --- the class's staff ----------------------------------------------------------------------------------

_ROW = f"""
    SELECT r.id, {seats.REQUEST_STATUS} AS status, r.student_member_id, u.full_name AS student_name,
           u.phone AS student_phone, c.id AS class_id, c.title AS class_title, r.class_month_id, m.month_start,
           r.student_note, r.decision_note, r.created_at, r.decided_at, r.held_until, c.teacher_member_id
    FROM seat_requests r
    JOIN classes c ON c.id = r.class_id
    LEFT JOIN class_months m ON m.id = r.class_month_id
    JOIN tenant_members tm ON tm.id = r.student_member_id
    JOIN users u ON u.id = tm.user_id
"""


async def _row(session: AsyncSession, r: Any) -> SeatRequestRow:
    s = await seats.seating(session, r.class_id, r.class_month_id, r.student_member_id)
    data = {k: getattr(r, k) for k in SeatRequestRow.model_fields if k != "seats_free"}
    return SeatRequestRow(**data, seats_free=None if s.limit is None else max(0, s.limit - s.others))


async def inbox(session: AsyncSession, actor: Actor, status: str) -> list[SeatRequestRow]:
    rows = (await session.execute(text(f"""
        SELECT * FROM ({_ROW}) x
        WHERE x.status = :st AND (CAST(:teacher AS uuid) IS NULL OR x.teacher_member_id = :teacher)
        ORDER BY x.created_at {"ASC" if status == "pending" else "DESC"} LIMIT 200
    """), {"st": status, "teacher": None if actor.manages_all else actor.auth.member_id})).all()
    return [await _row(session, r) for r in rows]


async def decide(session: AsyncSession, actor: Actor, request_id: UUID, body: SeatDecision) -> SeatRequestRow:
    r = (await session.execute(text(f"{_ROW} WHERE r.id = :id"), {"id": request_id})).one_or_none()
    if r is None or not (actor.manages_all or r.teacher_member_id == actor.auth.member_id):
        raise ApiError("NOT_FOUND", "Request not found.", status_code=404)
    # The class first (it is what serializes seats), then the request as it is now.
    await seats.lock(session, r.class_id)
    r = (await session.execute(text(f"{_ROW} WHERE r.id = :id FOR UPDATE OF r"), {"id": request_id})).one()
    allowed = ("pending", "rejected", "expired") if body.decision == "approve" else ("pending", "approved")
    if r.status not in allowed:
        raise ApiError("REQUEST_DECIDED", "This request was already answered.", status_code=409)
    held_until: datetime | None = None
    if body.decision == "approve":
        await _check_month(session, await _open_class(session, r.class_id), r.class_month_id)
        active = (await session.execute(text("SELECT status = 'active' FROM tenant_members WHERE id = :m"),
                                        {"m": r.student_member_id})).scalar_one()
        if not active:
            raise ApiError("STUDENT_INVALID", "This student is suspended here.", status_code=409)
        s = await seats.seating(session, r.class_id, r.class_month_id, r.student_member_id)
        if s.full and not s.mine:
            raise ApiError("CLASS_FULL", "Every seat is taken. Add a seat first.", status_code=409)
        held_until = datetime.now(UTC) + timedelta(hours=get_settings().seat_request_hold_hours)
    await session.execute(text("""
        UPDATE seat_requests SET status = :st, decided_by = :by, decided_at = now(), decision_note = :note,
                                 held_until = :until
        WHERE id = :id
    """), {"st": "approved" if body.decision == "approve" else "rejected", "by": actor.auth.member_id,
           "note": (body.note or "").strip() or None, "until": held_until, "id": r.id})
    await write_audit(session, actor_user_id=actor.auth.user_id, action=f"seat_request.{body.decision}",
                      entity_type="seat_request", entity_id=r.id, ip=actor.ip,
                      details={"student_member_id": r.student_member_id, "class_id": r.class_id,
                               "class_month_id": r.class_month_id, "held_until": held_until})
    return await _row(session, (await session.execute(text(f"{_ROW} WHERE r.id = :id"), {"id": r.id})).one())
