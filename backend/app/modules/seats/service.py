"""Seats and registration for tuition classes (docs/SEATS.md). Every rule about seats lives here, and the counting in the
SQL functions it shares with the public view (migration 0020: seat_holders, seat_last_month, seat_registration); nothing
else counts them. Runs in the class's tenant transaction.

A seat of a class (of a month, when it is monthly) is taken by
  * active access that takes a seat: paid, scholarship, manual, or free while still enrolled
  * a payment running now: a pending order whose hold hasn't ended
  * an accepted request not paid yet, until its time passes
  * a returning student who hasn't renewed yet, until the renewal date (monthly classes)
One student never counts twice. Holds, accepted requests and kept seats stop counting by themselves when their time
passes, so no job is needed.

A returning student has a seat in the class's previous month (the latest earlier one that was ever open, so a holiday
without a month breaks nothing) and hasn't left since. Their seat is kept only if they had it before this month
opened: joining last month later makes them a continuing student (registration doesn't apply to them) without a kept
seat, otherwise two open months could promise more seats than exist.

`check()` is read-only (cart, prices). Taking a seat goes through `hold()`, or `lock()` and then a check: the class row
is locked first and only then are the seats counted, so two students can never both get the last one.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.errors import ApiError
from app.modules.auth.dependencies import Actor
from app.modules.catalog.service import load_class
from app.modules.seats.schemas import KeepIn, Lapsed, Seat, SeatRequestInfo, SeatsOut, SeatState

MAX_KEEP_DAYS = 60

# Everyone with a seat of class :c (month :mo, or NULL): one row per reason. A student may appear twice.
_TAKEN = "SELECT * FROM seat_holders(CAST(:c AS uuid), CAST(:mo AS uuid))"
_LAST_MONTH = "seat_last_month(CAST(:c AS uuid), CAST(:mo AS uuid))"

# When a student appears twice, the stronger reason is shown.
_KINDS = ("access", "paying", "accepted", "kept")


@dataclass(frozen=True, slots=True)
class Seating:
    """A class's seats for one month (or the class) as one student would find them."""

    kind: str
    limit: int | None
    show_count: bool
    registration: str            # effective today
    taken: int                   # everyone
    others: int                  # everyone but this student
    mine: bool                   # this student has a seat or holds one

    @property
    def full(self) -> bool:
        """No seat left for this student."""
        return self.limit is not None and self.others >= self.limit


async def lock(session: AsyncSession, class_id: UUID) -> None:
    """Serializes taking seats of one class until the transaction ends. NO KEY: rows that only reference the class
    (other students' grants, orders, enrolments) can still be written meanwhile."""
    await session.execute(text("SELECT 1 FROM classes WHERE id = :c FOR NO KEY UPDATE"), {"c": class_id})


async def seating(session: AsyncSession, class_id: UUID, month_id: UUID | None, member_id: UUID | None) -> Seating:
    r = (await session.execute(text(f"""
        WITH taken AS ({_TAKEN})
        SELECT c.kind, c.seat_limit, c.show_seat_count,
               seat_registration(c.registration, c.registration_after_start, c.starts_on) AS registration,
               (SELECT count(DISTINCT student_member_id) FROM taken) AS taken,
               (SELECT count(DISTINCT student_member_id) FROM taken
                WHERE student_member_id IS DISTINCT FROM CAST(:m AS uuid)) AS others,
               EXISTS (SELECT 1 FROM taken WHERE student_member_id = CAST(:m AS uuid)) AS mine
        FROM classes c WHERE c.id = :c
    """), {"c": class_id, "mo": month_id, "m": member_id})).one()
    return Seating(kind=r.kind, limit=r.seat_limit, show_count=r.show_seat_count, registration=r.registration,
                   taken=r.taken, others=r.others, mine=r.mine)


async def check(session: AsyncSession, class_id: UUID, month_id: UUID | None, member_id: UUID | None) -> None:
    """May this student take a seat now? Raises when not. Callers handle access they already have, and past months
    (which take no seat), before this."""
    await _check(session, await seating(session, class_id, month_id, member_id), class_id, month_id, member_id)


async def _check(session: AsyncSession, s: Seating, class_id: UUID, month_id: UUID | None,
                 member_id: UUID | None) -> None:
    if s.kind != "tuition" or s.mine:
        return
    if s.full:
        raise ApiError("CLASS_FULL", "Every seat in this class is taken.", status_code=409)
    if s.registration == "open" or await is_continuing(session, class_id, month_id, member_id):
        return
    if s.registration == "ask":
        raise ApiError("SEAT_REQUEST_REQUIRED", "Ask the teacher for a seat first.", status_code=409)
    raise ApiError("REGISTRATION_CLOSED", "This class isn't taking new students now.", status_code=409)


async def is_continuing(session: AsyncSession, class_id: UUID, month_id: UUID | None, member_id: UUID | None) -> bool:
    """A continuing student (see the top of this file). Registration is about new students only."""
    if month_id is None or member_id is None:
        return False
    return bool((await session.execute(text(
        f"SELECT EXISTS (SELECT 1 FROM {_LAST_MONTH} l WHERE l.student_member_id = :m AND l.stayed)"),
        {"c": class_id, "mo": month_id, "m": member_id})).scalar_one())


async def hold(session: AsyncSession, class_id: UUID, month_id: UUID | None, member_id: UUID) -> datetime:
    """Takes a seat while the student pays, in the transaction that creates their order. Returns when it ends.
    Starting again while a hold runs keeps its end (never longer), and a class with limited seats gives a student only
    a few holds a day, so nobody can keep a seat blocked by restarting payment. A declined payment uses none up."""
    cfg = get_settings()
    await lock(session, class_id)
    await check(session, class_id, month_id, member_id)
    mine = (await session.execute(text("""
        SELECT max(o.seat_held_until) FILTER (
                   WHERE o.status = 'pending' AND o.seat_held_until > now()
                     AND i.class_month_id IS NOT DISTINCT FROM CAST(:mo AS uuid)) AS running,
               count(DISTINCT (i.class_month_id, o.seat_held_until)) FILTER (
                   WHERE o.status IN ('pending', 'cancelled')) AS used,
               (SELECT seat_limit IS NOT NULL FROM classes WHERE id = :c) AS limited
        FROM orders o JOIN order_items i ON i.order_id = o.id
        WHERE o.student_member_id = :m AND i.class_id = :c AND o.seat_held_until IS NOT NULL
          AND o.created_at > now() - interval '1 day'
    """), {"m": member_id, "c": class_id, "mo": month_id})).one()
    if mine.running is not None:
        return mine.running  # type: ignore[no-any-return]
    if mine.limited and mine.used >= cfg.seat_holds_per_day:
        raise ApiError("SEAT_HOLD_LIMIT", "You started paying for this class several times without finishing. "
                       "Please try again tomorrow, or contact us.", status_code=409)
    return datetime.now(UTC) + timedelta(minutes=cfg.seat_hold_minutes)


async def over_limit(session: AsyncSession, class_id: UUID, month_id: UUID | None, member_id: UUID) -> bool:
    """Would a seat for this student go over the limit? (Lock first.) For seats that are given anyway: a payment that
    arrives after its hold ended, and staff giving access."""
    s = await seating(session, class_id, month_id, member_id)
    return s.kind == "tuition" and not s.mine and s.full


async def seated(session: AsyncSession, class_id: UUID, month_id: UUID | None, member_id: UUID) -> None:
    """A student just got a seat (paid, joined a free class, or was given access): their request is used, and they
    aren't waiting for one any more."""
    await session.execute(text("""
        UPDATE seat_requests SET status = 'used'
        WHERE class_id = :c AND class_month_id IS NOT DISTINCT FROM CAST(:mo AS uuid) AND student_member_id = :m
          AND status IN ('pending', 'approved')
    """), {"c": class_id, "mo": month_id, "m": member_id})
    await session.execute(text("DELETE FROM seat_waits WHERE class_id = :c AND student_member_id = :m"),
                          {"c": class_id, "m": member_id})


# --- what a student sees ---------------------------------------------------------------------------

async def state(session: AsyncSession, class_id: UUID, month_id: UUID | None, member_id: UUID | None) -> SeatState:
    """Can this student pay for (or join) this now, and if not, why? Numbers only when the teacher shows them."""
    s = await seating(session, class_id, month_id, member_id)
    problem: str | None = None
    try:
        await _check(session, s, class_id, month_id, member_id)
    except ApiError as exc:
        problem = exc.code
    held = {r.kind: r.held_until for r in (await session.execute(text(
        f"SELECT h.kind, max(h.held_until) AS held_until FROM ({_TAKEN}) h WHERE h.student_member_id = :m GROUP BY h.kind"),
        {"c": class_id, "mo": month_id, "m": member_id})).all()} if s.mine else {}
    request = (await session.execute(text(f"""
        SELECT r.status, {REQUEST_STATUS} AS effective, r.held_until, r.decision_note, r.created_at FROM seat_requests r
        WHERE r.class_id = :c AND r.class_month_id IS NOT DISTINCT FROM CAST(:mo AS uuid) AND r.student_member_id = :m
          AND r.status NOT IN ('withdrawn', 'used')
    """), {"c": class_id, "mo": month_id, "m": member_id})).one_or_none() if member_id else None
    shown = s.limit is not None and s.show_count
    return SeatState(
        limited=s.limit is not None, limit=s.limit if shown else None, left=max(0, s.limit - s.taken) if shown and s.limit is not None else None,
        full=s.limit is not None and s.taken >= s.limit, registration=s.registration, problem=problem,
        paying_until=held.get("paying") if s.limit is not None else None, kept_until=held.get("kept") if s.limit is not None else None,
        request=SeatRequestInfo(status=request.effective, held_until=request.held_until,
                                decision_note=request.decision_note, created_at=request.created_at) if request else None)


# An accepted request whose time passed is `expired` without anything having to mark it.
REQUEST_STATUS = "CASE WHEN r.status = 'approved' AND r.held_until <= now() THEN 'expired' ELSE r.status END"


# --- the teacher's seat list ----------------------------------------------------------------------

async def class_seats(session: AsyncSession, actor: Actor, class_id: UUID, month_id: UUID | None) -> SeatsOut:
    c = await load_class(session, actor, class_id)
    if c.kind != "tuition":
        raise ApiError("NOT_FOUND", "Class not found.", status_code=404)
    if c.pricing_model == "monthly":
        if month_id is None:
            raise ApiError("MONTH_REQUIRED", "Choose the month.")
        if (await session.execute(text("SELECT 1 FROM class_months WHERE id = :mo AND class_id = :c"),
                                  {"mo": month_id, "c": c.id})).first() is None:
            raise ApiError("MONTH_INVALID", "That month does not belong to this class.")
    elif month_id is not None:
        raise ApiError("MONTH_INVALID", "Only monthly classes have seats per month.")
    s = await seating(session, c.id, month_id, None)
    # One line per student: the strongest reason.
    rows = (await session.execute(text(f"""
        WITH taken AS ({_TAKEN})
        SELECT DISTINCT ON (t.student_member_id) t.student_member_id, t.kind, t.source, t.since, t.held_until,
               u.full_name, u.phone
        FROM taken t
        JOIN tenant_members tm ON tm.id = t.student_member_id
        JOIN users u ON u.id = tm.user_id
        ORDER BY t.student_member_id, array_position(CAST(:kinds AS text[]), t.kind), t.held_until DESC
    """), {"c": c.id, "mo": month_id, "kinds": list(_KINDS)})).all()
    seats = sorted((Seat(member_id=r.student_member_id, full_name=r.full_name, phone=r.phone, kind=r.kind,
                         source=r.source, since=r.since, held_until=r.held_until) for r in rows),
                   key=lambda x: (_KINDS.index(x.kind), x.full_name.lower()))
    # Last month's students without a seat this month: too late, released, or joined after it opened.
    lapsed: list[Lapsed] = []
    if month_id is not None:
        here = {x.member_id for x in seats}
        lapsed = [Lapsed(member_id=r.student_member_id, full_name=r.full_name, phone=r.phone, released=r.released)
                  for r in (await session.execute(text(f"""
                      SELECT l.student_member_id, u.full_name, u.phone, COALESCE(l.action = 'release', false) AS released
                      FROM {_LAST_MONTH} l
                      JOIN tenant_members tm ON tm.id = l.student_member_id JOIN users u ON u.id = tm.user_id
                      ORDER BY u.full_name
                  """), {"c": c.id, "mo": month_id})).all() if r.student_member_id not in here]
    waiting = (await session.execute(text("SELECT count(*) FROM seat_waits WHERE class_id = :c"),
                                     {"c": c.id})).scalar_one()
    return SeatsOut(limit=s.limit, taken=s.taken,
                    free=None if s.limit is None else max(0, s.limit - s.taken),
                    over_by=0 if s.limit is None else max(0, s.taken - s.limit),
                    registration=s.registration, seats=seats, lapsed=lapsed, waiting=waiting)


async def decide_keep(session: AsyncSession, actor: Actor, month_id: UUID, member_id: UUID, body: KeepIn) -> SeatsOut:
    """Staff keep one student's seat in this month for longer (or again), or release it before the renewal date."""
    class_id = await _month_class(session, actor, month_id)
    await lock(session, class_id)
    p = {"c": class_id, "mo": month_id, "m": member_id}
    if (await session.execute(text(f"""
        SELECT 1 FROM {_LAST_MONTH} l WHERE l.student_member_id = :m
    """), p)).first() is None:
        raise ApiError("NOT_RETURNING", "Only a student of the class's previous month can have a kept seat.", 409)
    s = await seating(session, class_id, month_id, member_id)
    has = (await session.execute(text(f"""
        SELECT kind FROM ({_TAKEN}) t WHERE t.student_member_id = :m AND kind = 'access' LIMIT 1
    """), p)).first()
    if has is not None:
        raise ApiError("ALREADY_HAS_ACCESS", "This student already has this month.", status_code=409)
    if body.action == "keep":
        assert body.keep_until is not None
        if not datetime.now(UTC) < body.keep_until <= datetime.now(UTC) + timedelta(days=MAX_KEEP_DAYS):
            raise ApiError("KEEP_UNTIL_INVALID", f"Choose a time in the next {MAX_KEEP_DAYS} days.", status_code=422)
        if not s.mine and s.full and not body.allow_over_limit:
            raise ApiError("CLASS_FULL", "Every seat is taken. Confirm to go over the limit.", status_code=409)
    await session.execute(text("""
        INSERT INTO seat_keeps (tenant_id, class_id, class_month_id, student_member_id, action, keep_until, decided_by)
        VALUES (current_tenant_id(), :c, :mo, :m, :a, :until, :by)
        ON CONFLICT (class_month_id, student_member_id) DO UPDATE
        SET action = EXCLUDED.action, keep_until = EXCLUDED.keep_until, decided_by = EXCLUDED.decided_by, decided_at = now()
    """), {**p, "a": body.action, "until": body.keep_until, "by": actor.auth.member_id})
    await write_audit(session, actor_user_id=actor.auth.user_id, action=f"seat.{body.action}", entity_type="class_month",
                      entity_id=month_id, ip=actor.ip,
                      details={"student_member_id": member_id, "keep_until": body.keep_until,
                               "over_limit": body.action == "keep" and not s.mine and s.full})
    return await class_seats(session, actor, class_id, month_id)


async def clear_keep(session: AsyncSession, actor: Actor, month_id: UUID, member_id: UUID, *,
                     allow_over_limit: bool) -> SeatsOut:
    """Back to the ordinary rule for this student. Undoing a release may bring a kept seat back."""
    class_id = await _month_class(session, actor, month_id)
    await lock(session, class_id)
    before = await seating(session, class_id, month_id, member_id)
    gone = (await session.execute(text(
        "DELETE FROM seat_keeps WHERE class_month_id = :mo AND student_member_id = :m RETURNING action"),
        {"mo": month_id, "m": member_id})).first()
    if gone is not None:
        back = not before.mine and (await seating(session, class_id, month_id, member_id)).mine
        if back and before.full and not allow_over_limit:
            raise ApiError("CLASS_FULL", "Every seat is taken. Confirm to go over the limit.", status_code=409)
        await write_audit(session, actor_user_id=actor.auth.user_id, action="seat.keep_clear", entity_type="class_month",
                          entity_id=month_id, details={"student_member_id": member_id, "was": gone.action}, ip=actor.ip)
    return await class_seats(session, actor, class_id, month_id)


async def _month_class(session: AsyncSession, actor: Actor, month_id: UUID) -> UUID:
    """The class of an open month the actor manages."""
    m = (await session.execute(text("SELECT class_id, status FROM class_months WHERE id = :mo"),
                               {"mo": month_id})).one_or_none()
    if m is None:
        raise ApiError("NOT_FOUND", "Month not found.", status_code=404)
    try:
        c = await load_class(session, actor, m.class_id)
    except ApiError:
        raise ApiError("NOT_FOUND", "Month not found.", status_code=404) from None
    if m.status != "open":
        raise ApiError("MONTH_NOT_OPEN", "Seats are kept only in an open month.", status_code=409)
    return c.id
