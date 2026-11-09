"""Coupons (docs/COURSES.md section C.7, step C5).

- Courses only (v1). A coupon belongs to one organization: for one course, or every course it sells. A code only
  discounts items of its own organization, so one cart can hold codes of several teachers.
- Percent (basis points, rounded half up like commission) or a fixed amount; the price never goes below 0.
- A public coupon is an automatic sale price. Each item takes the single best discount: the student's typed code or
  the public sale, whichever leaves the lower price. No stacking.
- Coupons always expire, at most 90 days after they start. redeemed_count goes up when the order is paid (in the
  fulfilment transaction), not at checkout; checkout re-checks the limit, and a paid order is always honoured.
- Commission is charged on the amount actually paid (order_items.amount_cents), as for every sale.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.tenancy import tenant_transaction
from app.modules.auth.dependencies import Actor
from app.modules.catalog.schemas import _Patch

MAX_DAYS = 90

_USABLE = """k.status = 'active' AND now() >= k.starts_at AND now() < k.ends_at
             AND (k.max_redemptions IS NULL OR k.redeemed_count < k.max_redemptions)"""


@dataclass(frozen=True, slots=True)
class Discount:
    coupon_id: UUID
    code: str
    cents: int
    is_public: bool
    ends_at: datetime


def discount_cents(price: int, discount_type: str, percent_bps: int | None, amount_cents: int | None) -> int:
    if discount_type == "percent":
        return min(price, (price * (percent_bps or 0) + 5000) // 10000)
    return min(price, amount_cents or 0)


def normalize(code: str | None) -> str | None:
    code = (code or "").strip().upper()
    return code or None


async def best_discount(session: AsyncSession, class_id: UUID, price: int, code: str | None) -> Discount | None:
    """In the course's tenant transaction: the best usable discount for this course right now, from the public
    sale coupons and the typed code (if it belongs to this organization and applies to this course)."""
    rows = (await session.execute(text(f"""
        SELECT k.id, k.code::text AS code, k.discount_type, k.percent_bps, k.amount_cents, k.is_public, k.ends_at
        FROM coupons k
        WHERE (k.class_id = :c OR k.class_id IS NULL) AND {_USABLE}
          AND (k.is_public OR k.code = CAST(:code AS citext))
    """), {"c": class_id, "code": normalize(code)})).all()
    best: Discount | None = None
    for r in rows:
        cents = discount_cents(price, r.discount_type, r.percent_bps, r.amount_cents)
        if cents > 0 and (best is None or cents > best.cents or (cents == best.cents and not r.is_public)):
            best = Discount(coupon_id=r.id, code=r.code, cents=cents, is_public=r.is_public, ends_at=r.ends_at)
    return best


async def code_applies(session: AsyncSession, class_id: UUID, code: str) -> bool:
    """Whether a typed code is usable for this course now (for the cart's "Apply" and the course page's ?coupon=)."""
    return (await session.execute(text(f"""
        SELECT EXISTS (SELECT 1 FROM coupons k
                       WHERE k.code = CAST(:code AS citext) AND (k.class_id = :c OR k.class_id IS NULL) AND {_USABLE})
    """), {"c": class_id, "code": normalize(code)})).scalar_one()


async def redeem(session: AsyncSession, coupon_id: UUID) -> None:
    """Counted when the order is paid (fulfilment transaction). A paid order is honoured even past the limit."""
    await session.execute(text("UPDATE coupons SET redeemed_count = redeemed_count + 1 WHERE id = :id"),
                          {"id": coupon_id})


# --- the console ----------------------------------------------------------------------------

class CouponCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[A-Za-z0-9-]{4,20}$")
    course_id: UUID | None = None                # None = every course of the organization (owners and admins)
    discount_type: Literal["percent", "fixed"]
    percent_bps: int | None = Field(default=None, ge=1, le=10000)
    amount_cents: int | None = Field(default=None, gt=0, le=10**12)
    is_public: bool = False
    max_redemptions: int | None = Field(default=None, gt=0, le=1_000_000)
    starts_at: AwareDatetime | None = None       # default: now
    ends_at: AwareDatetime

    @field_validator("code")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class CouponUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = ("status", "ends_at")

    status: Literal["active", "disabled"] | None = None
    ends_at: AwareDatetime | None = None
    max_redemptions: int | None = Field(default=None, gt=0, le=1_000_000)


class CouponOut(BaseModel):
    id: UUID
    code: str
    course_id: UUID | None
    course_title: str | None                     # None = every course
    discount_type: str
    percent_bps: int | None
    amount_cents: int | None
    is_public: bool
    max_redemptions: int | None
    redeemed_count: int
    starts_at: datetime
    ends_at: datetime
    status: str
    state: str                                   # active | scheduled | expired | used_up | disabled
    created_at: datetime


_SELECT = """
    SELECT k.id, k.code::text AS code, k.class_id AS course_id, c.title AS course_title, k.discount_type,
           k.percent_bps, k.amount_cents, k.is_public, k.max_redemptions, k.redeemed_count, k.starts_at, k.ends_at,
           k.status, k.created_at,
           CASE WHEN k.status = 'disabled' THEN 'disabled'
                WHEN now() >= k.ends_at THEN 'expired'
                WHEN k.max_redemptions IS NOT NULL AND k.redeemed_count >= k.max_redemptions THEN 'used_up'
                WHEN now() < k.starts_at THEN 'scheduled'
                ELSE 'active' END AS state
    FROM coupons k LEFT JOIN classes c ON c.id = k.class_id
"""


def _out(r: Any) -> CouponOut:
    return CouponOut.model_validate(dict(r._mapping))


async def list_coupons(session: AsyncSession, actor: Actor) -> list[CouponOut]:
    """Owners and admins see every coupon; a teacher sees the coupons of the courses they teach."""
    rows = (await session.execute(text(_SELECT + """
        WHERE CAST(:teacher AS uuid) IS NULL OR c.teacher_member_id = :teacher
        ORDER BY k.created_at DESC
    """), {"teacher": None if actor.manages_all else actor.auth.member_id})).all()
    return [_out(r) for r in rows]


async def _load(session: AsyncSession, actor: Actor, coupon_id: UUID) -> Any:
    r = (await session.execute(text(_SELECT + " WHERE k.id = :id"), {"id": coupon_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Coupon not found.", status_code=404)
    if not actor.manages_all:
        teacher = (await session.execute(text("SELECT teacher_member_id FROM classes WHERE id = :c"),
                                         {"c": r.course_id})).scalar_one_or_none() if r.course_id else None
        if teacher != actor.auth.member_id:
            raise ApiError("NOT_FOUND", "Coupon not found.", status_code=404)
    return r


def _check_dates(starts: datetime, ends: datetime) -> None:
    if ends <= starts:
        raise ApiError("COUPON_DATES", "The end must be after the start.", status_code=422)
    if ends - starts > timedelta(days=MAX_DAYS):
        raise ApiError("COUPON_TOO_LONG", f"A coupon can last at most {MAX_DAYS} days.", status_code=422)


async def create_coupon(session: AsyncSession, actor: Actor, body: CouponCreate) -> CouponOut:
    if (body.discount_type == "percent") != (body.percent_bps is not None) or \
            (body.discount_type == "fixed") != (body.amount_cents is not None):
        raise ApiError("COUPON_VALUE_INVALID", "Give a percentage for a percent coupon, or an amount for a fixed one.", 422)
    if body.course_id is None:
        if not actor.manages_all:
            raise ApiError("ACCESS_DENIED", "Only owners and admins can make a coupon for every course.", 403)
    else:
        c = (await session.execute(text("SELECT kind, teacher_member_id FROM classes WHERE id = :c"),
                                   {"c": body.course_id})).one_or_none()
        if c is None or c.kind != "course" or not (actor.manages_all or c.teacher_member_id == actor.auth.member_id):
            raise ApiError("NOT_FOUND", "Course not found.", status_code=404)
    starts = body.starts_at or datetime.now(UTC)
    _check_dates(starts, body.ends_at)
    try:
        async with session.begin_nested():
            coupon_id = (await session.execute(text("""
                INSERT INTO coupons (class_id, code, discount_type, percent_bps, amount_cents, is_public, max_redemptions,
                                     starts_at, ends_at, created_by)
                VALUES (:c, :code, :type, :bps, :amt, :public, :max, COALESCE(CAST(:starts AS timestamptz), now()), :ends, :by)
                RETURNING id
            """), {"c": body.course_id, "code": body.code, "type": body.discount_type, "bps": body.percent_bps,
                   "amt": body.amount_cents, "public": body.is_public, "max": body.max_redemptions, "starts": body.starts_at,
                   "ends": body.ends_at, "by": actor.auth.member_id})).scalar_one()
    except IntegrityError as exc:
        raise ApiError("COUPON_CODE_TAKEN", "Your organization already has a coupon with this code.", 409) from exc
    await write_audit(session, actor_user_id=actor.auth.user_id, action="coupon.create", entity_type="coupon",
                      entity_id=coupon_id, details={"code": body.code, "course_id": body.course_id}, ip=actor.ip)
    return _out((await session.execute(text(_SELECT + " WHERE k.id = :id"), {"id": coupon_id})).one())


async def update_coupon(session: AsyncSession, actor: Actor, coupon_id: UUID, body: CouponUpdate) -> CouponOut:
    r = await _load(session, actor, coupon_id)
    changes = {k: v for k, v in body.changes().items() if getattr(r, k) != v}
    if "ends_at" in changes:
        _check_dates(r.starts_at, changes["ends_at"])
    if changes:
        sets = ", ".join(f"{k} = :{k}" for k in changes)
        await session.execute(text(f"UPDATE coupons SET {sets} WHERE id = :id"), {**changes, "id": coupon_id})
        await write_audit(session, actor_user_id=actor.auth.user_id, action="coupon.update", entity_type="coupon",
                          entity_id=coupon_id, details={"changes": changes}, ip=actor.ip)
    return _out((await session.execute(text(_SELECT + " WHERE k.id = :id"), {"id": coupon_id})).one())


async def public_discount(class_id: UUID, code: str | None) -> tuple[int, Discount | None] | None:
    """For anyone (a guest's cart, the course page's ?coupon=): (list price, best discount) of a public paid course,
    or None. Opens the course's tenant transaction only to read its coupons."""
    async with AppSession() as s:
        c = (await s.execute(text("""
            SELECT tenant_id, one_time_price_cents FROM public_courses
            WHERE id = :c AND pricing_model = 'one_time' AND one_time_price_cents > 0
        """), {"c": class_id})).one_or_none()
    if c is None:
        return None
    async with tenant_transaction(c.tenant_id) as session:
        return c.one_time_price_cents, await best_discount(session, class_id, c.one_time_price_cents, code)
