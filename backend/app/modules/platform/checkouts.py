"""Checkouts (migration phase 8): every cart payment across organizations, and a retry for one left half done.

A checkout is "stuck" when the gateway confirmed the payment but at least one of its orders was not fulfilled
(a tenant transaction failed). Until now only a repeated notification from the gateway finished it. Retry runs
the same fulfilment with the result already recorded on the checkout payment, so it books nothing twice: paid
orders are skipped, and each order is still booked exactly once by the ledger's unique indexes."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.pagination import decode_cursor, encode_cursor
from app.integrations.gateways.base import GatewayEvent
from app.modules.cart import service as cart
from app.modules.platform.auth import PlatformActor
from app.modules.platform.schemas import (
    CheckoutAttempt,
    CheckoutOrder,
    PlatformCheckout,
    PlatformCheckoutDetail,
    PlatformCheckoutPage,
    RetryResult,
)
from app.modules.platform.service import _audit

_SELECT = """
    SELECT c.id, c.checkout_no, c.status, c.user_id, u.full_name AS student_name, u.email::text AS student_email,
           u.phone AS student_phone, c.total_cents, c.currency, c.created_at, c.paid_at,
           cp.status AS payment_status,
           (SELECT count(*) FROM orders o WHERE o.checkout_id = c.id) AS orders,
           (SELECT count(*) FROM orders o WHERE o.checkout_id = c.id AND o.status = 'paid') AS orders_paid,
           (c.status = 'pending' AND EXISTS (SELECT 1 FROM checkout_payments x
                                             WHERE x.checkout_id = c.id AND x.status = 'succeeded')) AS stuck
    FROM checkouts c
    JOIN users u ON u.id = c.user_id
    LEFT JOIN LATERAL (SELECT status FROM checkout_payments x WHERE x.checkout_id = c.id
                       ORDER BY (x.status = 'succeeded') DESC, x.created_at DESC LIMIT 1) cp ON true
"""


def _pick(model: type[Any], r: Any) -> Any:
    return model.model_validate({k: getattr(r, k) for k in model.model_fields if hasattr(r, k)})


async def list_checkouts(session: AsyncSession, *, status: str | None, stuck: bool, cursor: str | None,
                         limit: int) -> PlatformCheckoutPage:
    after = decode_cursor(cursor) if cursor else None
    rows = (await session.execute(text(f"""
        SELECT * FROM ({_SELECT}) x
        WHERE (CAST(:st AS text) IS NULL OR x.status = :st)
          AND (NOT :stuck OR x.stuck)
          AND (CAST(:after_ts AS timestamptz) IS NULL OR (x.created_at, x.id) < (:after_ts, :after_id))
        ORDER BY x.created_at DESC, x.id DESC
        LIMIT :limit
    """), {"st": status, "stuck": stuck, "after_ts": after[0] if after else None,
           "after_id": after[1] if after else None, "limit": limit + 1})).all()
    page = rows[:limit]
    return PlatformCheckoutPage(
        items=[_pick(PlatformCheckout, r) for r in page],
        next_cursor=encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
    )


async def get_checkout(session: AsyncSession, checkout_id: UUID) -> PlatformCheckoutDetail:
    r = (await session.execute(text(_SELECT + " WHERE c.id = :id"), {"id": checkout_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Checkout not found.", status_code=404)
    orders = (await session.execute(text("""
        SELECT o.id AS order_id, o.order_no, o.status, o.tenant_id, t.name AS tenant_name, i.description,
               o.total_cents, p.gateway_fee_cents, o.paid_at
        FROM orders o
        JOIN tenants t ON t.id = o.tenant_id
        JOIN order_items i ON i.order_id = o.id
        LEFT JOIN payments p ON p.order_id = o.id AND p.checkout_payment_id IS NOT NULL
        WHERE o.checkout_id = :c ORDER BY o.created_at, o.id
    """), {"c": checkout_id})).all()
    attempts = (await session.execute(text("""
        SELECT id, gateway, idempotency_key, gateway_payment_ref, amount_cents, gateway_fee_cents, status, method,
               card_last4, failure_reason, created_at
        FROM checkout_payments WHERE checkout_id = :c ORDER BY created_at DESC
    """), {"c": checkout_id})).all()
    base = {k: getattr(r, k) for k in PlatformCheckout.model_fields}
    return PlatformCheckoutDetail(**base, order_list=[_pick(CheckoutOrder, o) for o in orders],
                                  attempts=[_pick(CheckoutAttempt, a) for a in attempts])


@dataclass
class _Paid:
    id: UUID
    gateway: str
    idempotency_key: str
    gateway_payment_ref: str | None
    amount_cents: int
    currency: str
    method: str | None
    card_last4: str | None


async def retry(session: AsyncSession, actor: PlatformActor, checkout_id: UUID) -> RetryResult:
    c = await get_checkout(session, checkout_id)
    if not c.stuck:
        raise ApiError("CHECKOUT_NOT_STUCK",
                       "Only a checkout paid at the gateway with orders still pending can be retried.",
                       status_code=409)
    r = (await session.execute(text("""
        SELECT cp.id, cp.gateway, cp.idempotency_key, cp.gateway_payment_ref, cp.amount_cents, c.currency,
               cp.method, cp.card_last4
        FROM checkout_payments cp JOIN checkouts c ON c.id = cp.checkout_id
        WHERE cp.checkout_id = :c AND cp.status = 'succeeded'
    """), {"c": checkout_id})).one()
    paid = _Paid(**r._mapping)
    # The gateway's confirmation, as already recorded. It is ours, so no signature to check again.
    event = GatewayEvent(
        gateway=paid.gateway, event_ref=f"retry:{paid.id}", payment_key=paid.idempotency_key, status="succeeded",
        amount_cents=paid.amount_cents, currency=paid.currency, gateway_payment_ref=paid.gateway_payment_ref,
        method=paid.method, card_last4=paid.card_last4, signature_ok=True, raw={},
    )
    try:
        outcome = await cart.apply_checkout_event(event, paid.id, checkout_id, c.user_id)
    except Exception as exc:
        outcome = f"error: {exc}"[:300]
    # Written whatever happened, so a failed retry is on the record too.
    await _audit(session, actor, "platform.checkout.retry", "checkout", checkout_id, {"outcome": outcome})
    return RetryResult(outcome=outcome, checkout=await get_checkout(session, checkout_id))
