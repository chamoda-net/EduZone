"""Orders, payments and the gateway webhook (CLAUDE.md section 8).

  1. Student clicks Pay -> order (pending) + one order item (commission and teacher
     snapshotted) + payment (initiated, unique idempotency key) -> redirect to the gateway.
  2. Gateway notifies us. The raw payload is stored first; then signature, amount and
     currency are checked; then, in ONE transaction: payment succeeded -> order paid ->
     access grant -> late request fulfilled -> ledger sale posting.
  3. The browser's return URL never grants anything; it only polls the order.
Webhooks may repeat or arrive out of order: every step is idempotent.
"""

import json
import logging
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.pagination import decode_cursor, encode_cursor
from app.core.tenancy import tenant_transaction
from app.integrations.gateways import Gateway, get_gateway
from app.integrations.gateways.base import CheckoutRequest, GatewayEvent
from app.modules.auth.dependencies import Actor, AuthContext
from app.modules.learning import access
from app.modules.learning import repository as learning_repo
from app.modules.ledger import posting
from app.modules.checkout.schemas import (
    CheckoutCreate,
    CheckoutOut,
    OrderItemOut,
    OrderOut,
    OrgOrderPage,
    OrgOrderRow,
    Redirect,
)

log = logging.getLogger("eduzone.checkout")

_ORDER_SELECT = """
    SELECT o.id, o.order_no, o.status, o.currency, o.total_cents, o.created_at, o.paid_at, o.student_member_id,
           i.id AS item_id, i.class_id, c.slug AS class_slug, i.class_month_id, i.description, i.amount_cents,
           i.teacher_member_id,
           (SELECT p.method FROM payments p WHERE p.order_id = o.id AND p.status = 'succeeded' LIMIT 1) AS method,
           (SELECT p.card_last4 FROM payments p WHERE p.order_id = o.id AND p.status = 'succeeded' LIMIT 1) AS card_last4
    FROM orders o
    JOIN order_items i ON i.order_id = o.id
    JOIN classes c ON c.id = i.class_id
"""


def _order_out(r: Any) -> OrderOut:
    return OrderOut(
        id=r.id, order_no=r.order_no, status=r.status, currency=r.currency, total_cents=r.total_cents,
        created_at=r.created_at, paid_at=r.paid_at, method=r.method, card_last4=r.card_last4,
        item=OrderItemOut(id=r.item_id, class_id=r.class_id, class_slug=r.class_slug,
                          class_month_id=r.class_month_id, description=r.description, amount_cents=r.amount_cents),
    )


def _month_label(d: Any) -> str:
    return d.strftime("%B %Y")


async def _new_order_no(session: AsyncSession) -> str:
    prefix = datetime.now(UTC).strftime("EZ-%y%m-")
    while True:
        candidate = prefix + secrets.token_hex(3).upper()
        exists = (await session.execute(text("SELECT 1 FROM orders WHERE order_no = :n"), {"n": candidate})).first()
        if not exists:
            return candidate


# --- 1. checkout ---------------------------------------------------------------------

async def create_checkout(session: AsyncSession, auth: AuthContext, site_host: str, body: CheckoutCreate,
                          gateway: Gateway) -> CheckoutOut:
    s = get_settings()
    c = (await session.execute(text("""
        SELECT id, slug, title, status, pricing_model, monthly_fee_cents, one_time_price_cents, teacher_member_id
        FROM classes WHERE id = :id
    """), {"id": body.class_id})).one_or_none()
    if c is None or c.status != "published":
        raise ApiError("NOT_FOUND", "Class not found.", status_code=404)
    tenant = (await session.execute(text(
        "SELECT currency, commission_bps FROM tenants WHERE id = current_tenant_id()"))).one()

    late_request_id: UUID | None = None
    if c.pricing_model == "free":
        raise ApiError("FREE_CLASS", "This class is free; join it instead.", status_code=409)
    if c.pricing_model == "monthly":
        if body.class_month_id is None:
            raise ApiError("MONTH_REQUIRED", "Choose the month to pay for.")
        m = (await session.execute(text("""
            SELECT id, month_start, status, fee_cents FROM class_months WHERE id = :id AND class_id = :c
        """), {"id": body.class_month_id, "c": c.id})).one_or_none()
        if m is None:
            raise ApiError("MONTH_INVALID", "That month does not belong to this class.")
        if m.status == "upcoming":
            raise ApiError("MONTH_NOT_OPEN", "This month is not open for payment yet.", status_code=409)
        if m.status == "closed":
            req = await learning_repo.late_request(session, auth.member_id, m.id)
            if req is None or req.status != "approved":
                raise ApiError("LATE_APPROVAL_REQUIRED", "Ask the teacher before paying for a past month.", 409)
            late_request_id = req.id
        amount = m.fee_cents if m.fee_cents is not None else c.monthly_fee_cents
        description = f"{c.title} - {_month_label(m.month_start)}"
    else:
        if body.class_month_id is not None:
            raise ApiError("MONTH_INVALID", "This class is paid once, not per month.")
        amount = c.one_time_price_cents
        description = c.title
    if not amount:
        raise ApiError("NOTHING_TO_PAY", "There is nothing to pay for this.", status_code=409)
    if await access.active_grant_for(session, auth.member_id, c.id, body.class_month_id) is not None:
        raise ApiError("ALREADY_HAS_ACCESS", "You already have access.", status_code=409)

    await learning_repo.upsert_enrollment(session, auth.member_id, c.id)
    order_id = (await session.execute(text("""
        INSERT INTO orders (tenant_id, student_member_id, order_no, currency, subtotal_cents, total_cents)
        VALUES (current_tenant_id(), :m, :no, :cur, :amt, :amt) RETURNING id
    """), {"m": auth.member_id, "no": await _new_order_no(session), "cur": tenant.currency, "amt": amount})).scalar_one()
    await session.execute(text("""
        INSERT INTO order_items (tenant_id, order_id, class_id, class_month_id, teacher_member_id, late_request_id,
                                 description, amount_cents, commission_bps)
        VALUES (current_tenant_id(), :o, :c, :mo, :t, :lr, :d, :amt, :bps)
    """), {"o": order_id, "c": c.id, "mo": body.class_month_id, "t": c.teacher_member_id, "lr": late_request_id,
           "d": description, "amt": amount, "bps": tenant.commission_bps})
    key = secrets.token_hex(16)
    await session.execute(text("""
        INSERT INTO payments (tenant_id, order_id, gateway, idempotency_key, amount_cents)
        VALUES (current_tenant_id(), :o, :g, :k, :amt)
    """), {"o": order_id, "g": gateway.name, "k": key, "amt": amount})

    who = await learning_repo.member_identity(session, auth.member_id)
    email = (await session.execute(text("SELECT email FROM users WHERE id = :u"), {"u": auth.user_id})).scalar_one()
    first, _, last = who.full_name.partition(" ")
    back = f"{s.site_scheme}://{site_host}/checkout/{order_id}"
    redirect = gateway.create_checkout(CheckoutRequest(
        payment_key=key, amount_cents=amount, currency=tenant.currency, description=description,
        first_name=first, last_name=last or first, email=email or "", phone=who.phone or "",
        return_url=back, cancel_url=back, notify_url=f"{s.api_public_url}/api/v1/webhooks/{gateway.name}",
    ))
    order = await get_order(session, auth, order_id)
    return CheckoutOut(order=order, redirect=Redirect(method=redirect.method, url=redirect.url, fields=redirect.fields))


async def get_order(session: AsyncSession, auth: AuthContext, order_id: UUID) -> OrderOut:
    r = (await session.execute(text(f"{_ORDER_SELECT} WHERE o.id = :id"), {"id": order_id})).one_or_none()
    if r is None or r.student_member_id != auth.member_id:
        raise ApiError("NOT_FOUND", "Order not found.", status_code=404)
    return _order_out(r)


async def my_orders(session: AsyncSession, auth: AuthContext) -> list[OrderOut]:
    rows = (await session.execute(text(f"""
        {_ORDER_SELECT} WHERE o.student_member_id = :m AND o.status <> 'pending'
        ORDER BY o.created_at DESC LIMIT 100
    """), {"m": auth.member_id})).all()
    return [_order_out(r) for r in rows]


async def org_orders(session: AsyncSession, actor: Actor, *, status: str | None, cursor: str | None,
                     limit: int) -> OrgOrderPage:
    after = decode_cursor(cursor) if cursor else None
    rows = (await session.execute(text(f"""
        SELECT x.*, u.full_name AS student_name, u.phone AS student_phone FROM ({_ORDER_SELECT}) x
        JOIN tenant_members tm ON tm.id = x.student_member_id
        JOIN users u ON u.id = tm.user_id
        WHERE (CAST(:st AS text) IS NULL OR x.status = :st)
          AND (CAST(:teacher AS uuid) IS NULL OR x.teacher_member_id = :teacher)
          AND (CAST(:after_ts AS timestamptz) IS NULL OR (x.created_at, x.id) < (:after_ts, :after_id))
        ORDER BY x.created_at DESC, x.id DESC
        LIMIT :limit
    """), {"st": status, "teacher": None if actor.manages_all else actor.auth.member_id,
           "after_ts": after[0] if after else None, "after_id": after[1] if after else None,
           "limit": limit + 1})).all()
    page = rows[:limit]
    return OrgOrderPage(
        items=[OrgOrderRow(**_order_out(r).model_dump(), student_name=r.student_name, student_phone=r.student_phone)
               for r in page],
        next_cursor=encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
    )


# --- 2. webhook --------------------------------------------------------------------

class WebhookRejected(Exception):
    """The notification is not trustworthy (bad signature): answer 400, don't process."""


async def process_notification(gateway_name: str, form: dict[str, str]) -> str:
    """Store, verify, fulfil. Returns a short outcome for logs and tests."""
    event = get_gateway(gateway_name).verify_webhook(form)

    # 1. Store the raw payload first (unique per gateway + event): a repeat is a no-op.
    async with AppSession() as s, s.begin():
        row = (await s.execute(text("""
            INSERT INTO gateway_webhook_events (gateway, event_ref, payload, signature_ok)
            VALUES (:g, :ref, CAST(:payload AS jsonb), :ok)
            ON CONFLICT (gateway, event_ref) DO NOTHING
            RETURNING id
        """), {"g": event.gateway, "ref": event.event_ref, "payload": json.dumps(event.raw),
               "ok": event.signature_ok})).one_or_none()
        if row is None:
            existing = (await s.execute(text("""
                SELECT id, processed_at FROM gateway_webhook_events WHERE gateway = :g AND event_ref = :ref
            """), {"g": event.gateway, "ref": event.event_ref})).one()
            if existing.processed_at is not None:
                return "duplicate"
            event_row_id = existing.id
        else:
            event_row_id = row.id

    if not event.signature_ok:
        await _mark(event_row_id, "invalid signature")
        raise WebhookRejected("invalid signature")

    async with AppSession() as s:
        tenant_id = (await s.execute(text("SELECT resolve_payment_tenant(:g, :k)"),
                                     {"g": event.gateway, "k": event.payment_key})).scalar_one()
    if tenant_id is None:
        await _mark(event_row_id, "unknown payment")
        return "unknown payment"

    try:
        async with tenant_transaction(tenant_id) as session:
            outcome = await _apply(session, event)
    except Exception as exc:
        await _mark(event_row_id, f"error: {exc}"[:500], processed=False)
        raise
    await _mark(event_row_id, None if outcome in ("paid", "failed", "cancelled", "duplicate", "pending") else outcome)
    return outcome


async def _mark(event_row_id: UUID, error: str | None, *, processed: bool = True) -> None:
    async with AppSession() as s, s.begin():
        await s.execute(text("""
            UPDATE gateway_webhook_events
            SET processed_at = CASE WHEN :done THEN now() ELSE processed_at END, process_error = :err
            WHERE id = :id
        """), {"id": event_row_id, "err": error, "done": processed})


async def _apply(session: AsyncSession, event: GatewayEvent) -> str:
    p = (await session.execute(text("""
        SELECT p.id, p.status, p.amount_cents, o.id AS order_id, o.status AS order_status, o.total_cents,
               o.currency, o.student_member_id
        FROM payments p JOIN orders o ON o.id = p.order_id
        WHERE p.gateway = :g AND p.idempotency_key = :k
        FOR UPDATE OF p, o
    """), {"g": event.gateway, "k": event.payment_key})).one_or_none()
    if p is None:
        return "unknown payment"
    if event.status == "pending":
        return "pending"

    if event.status == "succeeded":
        if p.status == "succeeded":
            return "duplicate"
        # The amount and currency must match the order exactly.
        if event.amount_cents != p.total_cents or event.currency != p.currency:
            await session.execute(text("UPDATE payments SET failure_reason = 'amount mismatch' WHERE id = :id"),
                                  {"id": p.id})
            log.warning("payment %s: amount/currency mismatch (%s %s)", p.id, event.amount_cents, event.currency)
            return "amount mismatch"
        await _fulfil(session, p, event)
        return "paid"

    if event.status in ("failed", "cancelled"):
        if p.status == "succeeded":
            return "ignored: already paid"          # out of order: a late failure never undoes a payment
        await session.execute(text("""
            UPDATE payments SET status = :st, failure_reason = :why, gateway_payment_ref = COALESCE(:ref, gateway_payment_ref)
            WHERE id = :id
        """), {"st": event.status, "why": event.status, "ref": event.gateway_payment_ref, "id": p.id})
        await session.execute(text("UPDATE orders SET status = :st WHERE id = :id AND status = 'pending'"),
                              {"st": event.status, "id": p.order_id})
        return event.status

    return f"unhandled: {event.status}"


async def _fulfil(session: AsyncSession, p: Any, event: GatewayEvent) -> None:
    """One transaction: payment -> order -> access -> late request -> ledger."""
    s = get_settings()
    tenant = (await session.execute(text(
        "SELECT gateway_fee_bearer FROM tenants WHERE id = current_tenant_id()"))).one()
    fee = posting.estimate_fee_cents(p.total_cents, s.gateway_fee_estimate_bps)
    await session.execute(text("""
        UPDATE payments SET status = 'succeeded', gateway_payment_ref = :ref, method = :method,
                            card_last4 = :last4, gateway_fee_cents = :fee, failure_reason = NULL
        WHERE id = :id
    """), {"ref": event.gateway_payment_ref, "method": event.method, "last4": event.card_last4, "fee": fee,
           "id": p.id})
    await session.execute(text("UPDATE orders SET status = 'paid', paid_at = now() WHERE id = :id"),
                          {"id": p.order_id})

    items = (await session.execute(text("""
        SELECT id, class_id, class_month_id, teacher_member_id, late_request_id, amount_cents, commission_bps
        FROM order_items WHERE order_id = :o
    """), {"o": p.order_id})).all()
    entries: list[posting.Entry] = []
    for item in items:  # exactly one in v1, so the whole fee belongs to it
        if await access.active_grant_for(session, p.student_member_id, item.class_id, item.class_month_id) is None:
            await learning_repo.insert_grant(session, member_id=p.student_member_id, class_id=item.class_id,
                                             month_id=item.class_month_id, source="purchase", granted_by=None,
                                             order_item_id=item.id)
        else:
            # Paid twice for the same month (two tabs): money is booked; staff should refund one.
            log.warning("order %s paid for access the student already had; refund needed", p.order_id)
        if item.late_request_id is not None:
            await session.execute(text("UPDATE late_month_requests SET status = 'fulfilled' WHERE id = :id"),
                                  {"id": item.late_request_id})
        entries += posting.sale_entries(gross=item.amount_cents, fee=fee, commission_bps=item.commission_bps,
                                        fee_bearer=tenant.gateway_fee_bearer, order_item_id=item.id,
                                        teacher_member_id=item.teacher_member_id)
    await posting.post(session, kind="sale", entries=entries, payment_id=p.id)
    await write_audit(session, actor_user_id=None, action="order.paid", entity_type="order", entity_id=p.order_id,
                      details={"payment_id": p.id, "gateway": event.gateway, "amount_cents": p.total_cents})


async def settle_fee(session: AsyncSession, payment_id: UUID, actual_fee_cents: int) -> UUID | None:
    """True-up the estimated fee once the settlement report gives the real one (platform
    admin / reconciliation job, step 9). Booked at most once per payment."""
    p = (await session.execute(text("""
        SELECT p.id, p.gateway_fee_cents, i.id AS item_id, i.teacher_member_id, t.gateway_fee_bearer
        FROM payments p JOIN order_items i ON i.order_id = p.order_id JOIN tenants t ON t.id = p.tenant_id
        WHERE p.id = :id AND p.status = 'succeeded'
    """), {"id": payment_id})).one()
    entries = posting.fee_settlement_entries(estimated=p.gateway_fee_cents or 0, actual=actual_fee_cents,
                                             fee_bearer=p.gateway_fee_bearer, order_item_id=p.item_id,
                                             teacher_member_id=p.teacher_member_id)
    return await posting.post(session, kind="fee_settlement", entries=entries, payment_id=p.id)
