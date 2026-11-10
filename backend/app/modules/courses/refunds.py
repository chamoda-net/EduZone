"""Course refunds (docs/COURSES.md section 9, step C6). Built for courses first; tuition can reuse `finalize`.

The rule: a student may ask for a refund of a course they bought within 7 days of paying, while under 30% of it is
complete and before a certificate was issued. Such a request is approved at once when the student has had fewer
than 3 refunds (requested, approved or processed, any organization) in the last 90 days; otherwise it waits in
EduZone's refund queue. A purchase made free by a coupon has nothing to refund.

Processing, exactly once:
  1. the refund is `approved` (committed first, so a gateway refund is never lost to a rollback);
  2. the gateway refunds that item's amount from the checkout's payment (`Gateway.refund`, keyed by the refund id).
     A gateway that can't refund through its API (PayHere until its API is checked in the sandbox) answers
     "manual": staff refund in its portal and record the reference;
  3. `finalize`, in the organization's transaction: refund `processed`, the ledger `refund` posting (unique per
     refund), the grant revoked, any certificate revoked, the student's review hidden (rating recomputed), the order
     item, order and payment marked refunded.
The order's payment row is the one booked in the ledger; the gateway's reference lives on the checkout payment.
"""

from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.errors import ApiError
from app.core.tenancy import tenant_transaction, user_transaction
from app.integrations.gateways import get_gateway
from app.integrations.gateways.base import RefundResult
from app.modules.auth.dependencies import AuthContext, UserContext
from app.modules.courses import reviews
from app.modules.ledger import posting

WINDOW = timedelta(days=7)
MAX_PERCENT = 30                 # refundable while progress is below this
AUTO_LIMIT = 3                   # fewer refunds than this in AUTO_WINDOW: approved automatically
AUTO_WINDOW = timedelta(days=90)

TxFactory = Callable[[UUID], AbstractAsyncContextManager[AsyncSession]]

_MESSAGES = {
    "REFUND_WINDOW_PASSED": "Refunds are possible for 7 days after buying a course.",
    "REFUND_PROGRESS": "Refunds are possible while less than 30% of the course is complete.",
    "REFUND_CERTIFICATE": "A course with a certificate can't be refunded.",
    "REFUND_NOTHING_PAID": "Nothing was paid for this course, so there is nothing to refund.",
    "REFUND_NOT_BOUGHT": "You didn't buy this course.",
    "REFUND_OPEN": "You already asked for a refund of this course.",
}


class RefundIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=1000)


class RefundOut(BaseModel):
    id: UUID
    status: str                          # requested | approved | processed | rejected
    amount_cents: int
    currency: str
    reason: str
    auto_approved: bool
    decision_note: str | None
    created_at: datetime
    processed_at: datetime | None


class RefundInfo(BaseModel):
    """What the course player shows about refunds for this student."""

    eligible: bool
    blocked_by: str | None               # an error code above when not eligible (and no refund is open)
    deadline: datetime | None            # the end of the 7 days
    amount_cents: int | None
    currency: str | None
    refund: RefundOut | None             # the latest refund of this course, if any


_REFUND = """
    SELECT r.id, r.status, r.amount_cents, o.currency, r.reason, r.auto_approved, r.decision_note, r.created_at,
           r.processed_at
    FROM refunds r JOIN order_items i ON i.id = r.order_item_id JOIN orders o ON o.id = i.order_id
"""


async def _purchase(session: AsyncSession, member_id: UUID, course_id: UUID) -> Any:
    """The student's paid, not refunded purchase of this course (with its live grant), newest first."""
    return (await session.execute(text("""
        SELECT i.id AS item_id, i.amount_cents, o.id AS order_id, o.paid_at, o.currency, p.id AS payment_id
        FROM order_items i
        JOIN orders o ON o.id = i.order_id AND o.status = 'paid' AND o.student_member_id = :m
        JOIN payments p ON p.order_id = o.id AND p.status = 'succeeded'
        JOIN access_grants g ON g.order_item_id = i.id AND g.revoked_at IS NULL
        WHERE i.class_id = :c AND i.refunded_at IS NULL
        ORDER BY o.paid_at DESC LIMIT 1
    """), {"m": member_id, "c": course_id})).one_or_none()


async def refund_info(session: AsyncSession, auth: AuthContext, course_id: UUID, percent: int) -> RefundInfo | None:
    """None when the student never bought the course (nothing to say). Tenant transaction of the course."""
    if auth.member_id is None:
        return None
    latest = (await session.execute(text(_REFUND + """
        WHERE i.class_id = :c AND r.requested_by = :m ORDER BY r.created_at DESC LIMIT 1
    """), {"c": course_id, "m": auth.member_id})).one_or_none()
    refund = RefundOut.model_validate(dict(latest._mapping)) if latest else None
    bought = await _purchase(session, auth.member_id, course_id)
    if bought is None:
        return RefundInfo(eligible=False, blocked_by=None, deadline=None, amount_cents=None, currency=None,
                          refund=refund) if refund else None
    deadline = bought.paid_at + WINDOW
    blocked: str | None = None
    if refund and refund.status in ("requested", "approved"):
        blocked = "REFUND_OPEN"
    elif bought.amount_cents == 0:
        blocked = "REFUND_NOTHING_PAID"
    elif datetime.now(deadline.tzinfo) >= deadline:
        blocked = "REFUND_WINDOW_PASSED"
    elif percent >= MAX_PERCENT:
        blocked = "REFUND_PROGRESS"
    elif (await session.execute(text("""
        SELECT EXISTS (SELECT 1 FROM certificates WHERE class_id = :c AND student_member_id = :m AND revoked_at IS NULL)
    """), {"c": course_id, "m": auth.member_id})).scalar_one():
        blocked = "REFUND_CERTIFICATE"
    return RefundInfo(eligible=blocked is None, blocked_by=blocked, deadline=deadline,
                      amount_cents=bought.amount_cents, currency=bought.currency,
                      refund=refund)


async def recent_refunds(user_id: UUID) -> int:
    """The student's refunds (any organization) in the abuse window; rejected ones don't count."""
    async with user_transaction(user_id) as session:
        return (await session.execute(text("""
            SELECT count(*) FROM refunds WHERE status <> 'rejected' AND created_at > now() - make_interval(days => :d)
        """), {"d": AUTO_WINDOW.days})).scalar_one()


async def gateway_target(session: AsyncSession, refund_id: UUID) -> tuple[str, str | None]:
    """(gateway, its payment reference) for a refund: the checkout payment's, or the order payment's for a single-item
    Pay. Works in the student's user transaction (their own rows) and in an eduzone_admin transaction."""
    r = (await session.execute(text("""
        SELECT COALESCE(cp.gateway, p.gateway) AS gateway, COALESCE(cp.gateway_payment_ref, p.gateway_payment_ref) AS ref
        FROM refunds r JOIN payments p ON p.id = r.payment_id
        LEFT JOIN checkout_payments cp ON cp.id = p.checkout_payment_id
        WHERE r.id = :id
    """), {"id": refund_id})).one()
    return r.gateway, r.ref


# --- the student's request ----------------------------------------------------------------------

async def request_refund(user: UserContext, course_id: UUID, body: RefundIn) -> RefundOut:
    from app.modules.courses.student import _lectures, progress_of
    from app.modules.learn.service import in_tenant_of

    auto = await recent_refunds(user.user_id) < AUTO_LIMIT
    async with in_tenant_of("class", course_id, user) as (session, auth, _org):
        tenant_id: UUID = (await session.execute(text("SELECT current_tenant_id()"))).scalar_one()
        if auth.member_id is None:
            raise ApiError("REFUND_NOT_BOUGHT", _MESSAGES["REFUND_NOT_BOUGHT"], status_code=409)
        percent = progress_of(await _lectures(session, auth, course_id)).percent
        info = await refund_info(session, auth, course_id, percent)
        if info is None or not info.eligible:
            code = (info.blocked_by if info else None) or "REFUND_NOT_BOUGHT"
            raise ApiError(code, _MESSAGES.get(code, "This course can't be refunded."), status_code=409)
        bought = await _purchase(session, auth.member_id, course_id)
        assert bought is not None
        await session.execute(text("SELECT id FROM order_items WHERE id = :i FOR UPDATE"), {"i": bought.item_id})
        try:
            async with session.begin_nested():
                refund_id: UUID = (await session.execute(text("""
                    INSERT INTO refunds (tenant_id, payment_id, order_item_id, amount_cents, reason, status, requested_by,
                                         auto_approved, decided_at)
                    VALUES (current_tenant_id(), :p, :i, :amt, :why, :st, :m, :auto, CASE WHEN :auto THEN now() END)
                    RETURNING id
                """), {"p": bought.payment_id, "i": bought.item_id, "amt": bought.amount_cents, "why": body.reason.strip(),
                       "st": "approved" if auto else "requested", "m": auth.member_id, "auto": auto})).scalar_one()
        except IntegrityError as exc:
            raise ApiError("REFUND_OPEN", _MESSAGES["REFUND_OPEN"], status_code=409) from exc
        await write_audit(session, actor_user_id=user.user_id, action="refund.request", entity_type="refund",
                          entity_id=refund_id, details={"course_id": course_id, "auto_approved": auto,
                                                        "amount_cents": bought.amount_cents})
    if auto:
        async with user_transaction(user.user_id) as session:
            gateway, ref = await gateway_target(session, refund_id)
        await execute(tenant_id, refund_id, gateway, ref, tenant_transaction, actor_user_id=None)
    async with tenant_transaction(tenant_id) as session:
        row = (await session.execute(text(_REFUND + " WHERE r.id = :id"), {"id": refund_id})).one()
    return RefundOut.model_validate(dict(row._mapping))


# --- processing -----------------------------------------------------------------------------------

async def execute(tenant_id: UUID, refund_id: UUID, gateway: str, payment_ref: str | None, tx: TxFactory, *,
                  actor_user_id: UUID | None) -> str:
    """Refund an approved refund at the gateway, then finalize it. Returns processed | manual | failed (the last
    two leave it approved with `failure_reason` for the queue)."""
    async with tx(tenant_id) as session:
        r = (await session.execute(text("SELECT status, amount_cents, reason FROM refunds WHERE id = :id"),
                                   {"id": refund_id})).one()
    if r.status != "approved":
        return r.status
    result = await _call_gateway(gateway, payment_ref, r.amount_cents, refund_id, r.reason)
    async with tx(tenant_id) as session:
        if result.status == "processed":
            await finalize(session, refund_id, result.ref, actor_user_id=actor_user_id)
        else:
            await session.execute(text(
                "UPDATE refunds SET failure_reason = :why WHERE id = :id AND status = 'approved'"),
                {"id": refund_id, "why": f"{result.status}: {result.message or ''}"[:500]})
            await write_audit(session, actor_user_id=actor_user_id, action=f"refund.gateway_{result.status}",
                              entity_type="refund", entity_id=refund_id, details={"message": result.message})
    return result.status


async def _call_gateway(gateway: str, payment_ref: str | None, amount: int, refund_id: UUID,
                        reason: str) -> RefundResult:
    if not payment_ref:
        return RefundResult(status="manual", message="The payment has no gateway reference; refund it by hand.")
    try:
        gw = get_gateway(gateway)
    except ApiError:
        return RefundResult(status="manual", message=f"The {gateway} gateway is not set up here.")
    try:
        return await gw.refund(payment_ref, amount, str(refund_id), reason)
    except Exception as exc:  # a network error: try again later
        return RefundResult(status="failed", message=str(exc)[:300])


async def finalize(session: AsyncSession, refund_id: UUID, gateway_refund_ref: str | None, *,
                   actor_user_id: UUID | None) -> None:
    """The money went back: book it and take the course away. Idempotent (a processed refund is left alone)."""
    r = (await session.execute(text("""
        SELECT r.id, r.status, r.amount_cents, r.payment_id, r.requested_by, i.id AS item_id, i.class_id, i.order_id,
               i.amount_cents AS gross, i.commission_bps, i.teacher_member_id
        FROM refunds r JOIN order_items i ON i.id = r.order_item_id
        WHERE r.id = :id FOR UPDATE OF r
    """), {"id": refund_id})).one()
    if r.status == "processed":
        return
    if r.status != "approved":
        raise ApiError("REFUND_NOT_APPROVED", "Only an approved refund can be processed.", status_code=409)
    await session.execute(text("""
        UPDATE refunds SET status = 'processed', processed_at = now(), gateway_refund_ref = :ref, failure_reason = NULL
        WHERE id = :id
    """), {"id": refund_id, "ref": gateway_refund_ref})
    await posting.post(session, kind="refund", refund_id=refund_id, created_by=actor_user_id,
                       entries=posting.refund_entries(refund=r.amount_cents, gross=r.gross,
                                                      commission_bps=r.commission_bps, order_item_id=r.item_id,
                                                      teacher_member_id=r.teacher_member_id))
    params = {"i": r.item_id, "c": r.class_id, "m": r.requested_by}
    await session.execute(text("""
        UPDATE access_grants SET revoked_at = now(), revoke_reason = 'refunded'
        WHERE order_item_id = :i AND revoked_at IS NULL
    """), params)
    await session.execute(text("""
        UPDATE certificates SET revoked_at = now(), revoke_reason = 'refunded'
        WHERE class_id = :c AND student_member_id = :m AND revoked_at IS NULL
    """), params)
    hidden = await session.execute(text("""
        UPDATE course_reviews SET status = 'hidden', hidden_reason = 'Refunded'
        WHERE class_id = :c AND student_member_id = :m AND status = 'visible'
    """), params)
    if hidden.rowcount:
        await reviews.recompute_rating(session, r.class_id)
    await session.execute(text("UPDATE order_items SET refunded_at = now() WHERE id = :i"), params)
    await session.execute(text("UPDATE orders SET status = 'refunded' WHERE id = :o"), {"o": r.order_id})
    await session.execute(text("UPDATE payments SET status = 'refunded' WHERE id = :p"), {"p": r.payment_id})
    await write_audit(session, actor_user_id=actor_user_id, action="refund.processed", entity_type="refund",
                      entity_id=refund_id, details={"amount_cents": r.amount_cents, "gateway_ref": gateway_refund_ref})
