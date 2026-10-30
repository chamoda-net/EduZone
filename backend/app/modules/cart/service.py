"""The cart and one payment across teachers (migration phase 6, CLAUDE.md section 8).

  cart_items (per user) -> checkout: every item is priced in its own tenant (the same rules as the Pay button,
  `checkout.service.price_item`), then one `checkouts` row and one `checkout_payments` attempt for the total
  (user transaction), then one pending order per item in that item's tenant (tenant transactions).
  The gateway notifies once; the payment is recorded on the checkout first, then each order is fulfilled in its
  own tenant transaction with its share of the gateway fee (largest remainder, so the shares add up exactly).
  A failed order is left pending and retried when the notification comes again; nothing is refunded
  automatically. Never app.user_id and app.tenant_id in one transaction.
"""

import logging
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.tenancy import tenant_transaction, user_transaction
from app.integrations.gateways import Gateway
from app.integrations.gateways.base import CheckoutRequest, GatewayEvent
from app.modules.auth.dependencies import UserContext, ensure_student_member
from app.modules.cart.schemas import (
    MAX_CART_ITEMS,
    Cart,
    CartItemIn,
    CartItemOut,
    CheckoutDetail,
    CheckoutStarted,
)
from app.modules.checkout import service as checkout
from app.modules.checkout.schemas import OrderItemOut, OrderOut, Redirect
from app.modules.learn.service import in_tenant_of
from app.modules.learning.schemas import OrgRef
from app.modules.ledger import posting

log = logging.getLogger("eduzone.cart")

# Problems that mean the item can never be bought as it is (refused when adding).
_STRUCTURAL = {"UNAVAILABLE", "NOT_FOUND", "FREE_CLASS", "MONTH_REQUIRED", "MONTH_INVALID", "NOTHING_TO_PAY"}


# --- what an item is (public read path) ---------------------------------------------------

async def _public(session: AsyncSession, class_id: UUID, month_id: UUID | None) -> Any:
    return (await session.execute(text("""
        SELECT pc.id, pc.slug, pc.title, pc.subject_slug, pc.subject_name, pc.teacher_slug, pc.teacher_name,
               pc.teacher_photo_url, pc.org_slug, pc.org_name, pc.cover_image_url, pc.pricing_model,
               pc.one_time_price_cents, pc.currency,
               m.id AS month_id, m.month_start, m.status AS month_status, m.fee_cents AS month_fee_cents
        FROM public_classes pc
        LEFT JOIN public_class_months m ON m.class_id = pc.id AND m.id = CAST(:mo AS uuid)
        WHERE pc.id = :c
    """), {"c": class_id, "mo": month_id})).one_or_none()


def _public_problem(r: Any, month_id: UUID | None) -> str | None:
    """What anyone can tell from the public data (a guest's cart)."""
    if r.pricing_model == "free":
        return "FREE_CLASS"
    if r.pricing_model == "monthly":
        if month_id is None:
            return "MONTH_REQUIRED"
        if r.month_id is None:
            return "MONTH_INVALID"
        if r.month_status == "upcoming":
            return "MONTH_NOT_OPEN"
        if r.month_status == "closed":
            return "LATE_APPROVAL_REQUIRED"     # may be approved for a signed-in student
        return None
    return "MONTH_INVALID" if month_id is not None else None


def _item_out(item_id: UUID | None, class_id: UUID, month_id: UUID | None, r: Any,
              amount: int | None, problem: str | None) -> CartItemOut:
    if r is None:
        return CartItemOut(id=item_id, class_id=class_id, class_month_id=month_id, title="", path="/classes",
                           subject_name="", teacher_name="", teacher_photo_url=None, org=OrgRef(slug="", name=""),
                           cover_image_url=None, month_start=None, amount_cents=None, currency="LKR",
                           problem="UNAVAILABLE")
    return CartItemOut(
        id=item_id, class_id=class_id, class_month_id=month_id, title=r.title,
        path=f"/{r.subject_slug}/{r.teacher_slug}/{r.slug}", subject_name=r.subject_name,
        teacher_name=r.teacher_name, teacher_photo_url=r.teacher_photo_url, org=OrgRef(slug=r.org_slug, name=r.org_name),
        cover_image_url=r.cover_image_url, month_start=r.month_start, amount_cents=amount, currency=r.currency,
        problem=problem)


def _guest_amount(r: Any) -> int | None:
    return r.month_fee_cents if r.pricing_model == "monthly" else r.one_time_price_cents


async def _for_user(user: UserContext, class_id: UUID, month_id: UUID | None) -> tuple[int | None, str | None]:
    """(price, problem) for this student, decided in the class's tenant by the same rules as paying."""
    try:
        async with in_tenant_of("class", class_id, user) as (session, auth, _):
            priced = await checkout.price_item(session, auth, class_id, month_id)
        return priced.amount_cents, None
    except ApiError as exc:
        return None, "UNAVAILABLE" if exc.code == "NOT_FOUND" else exc.code


def _cart(items: list[CartItemOut]) -> Cart:
    ok = [i for i in items if i.problem is None and i.amount_cents is not None]
    return Cart(items=items, total_cents=sum(i.amount_cents or 0 for i in ok),
                currency=ok[0].currency if ok else "LKR",
                ready=bool(items) and len(ok) == len(items))


# --- cart ---------------------------------------------------------------------------------

async def _rows(user_id: UUID) -> list[Any]:
    async with user_transaction(user_id) as session:
        return list((await session.execute(text(
            "SELECT id, class_id, class_month_id FROM cart_items ORDER BY created_at, id"))).all())


async def get_cart(user: UserContext) -> Cart:
    items: list[CartItemOut] = []
    for row in await _rows(user.user_id):
        async with AppSession() as session:
            r = await _public(session, row.class_id, row.class_month_id)
        if r is None:
            items.append(_item_out(row.id, row.class_id, row.class_month_id, None, None, "UNAVAILABLE"))
            continue
        amount, problem = await _for_user(user, row.class_id, row.class_month_id)
        items.append(_item_out(row.id, row.class_id, row.class_month_id, r, amount, problem))
    return _cart(items)


async def preview(items: list[CartItemIn]) -> Cart:
    """A guest's cart (kept in the browser): public prices and what's visible without an account."""
    out: list[CartItemOut] = []
    async with AppSession() as session:
        for it in items[:MAX_CART_ITEMS]:
            r = await _public(session, it.class_id, it.class_month_id)
            problem = _public_problem(r, it.class_month_id) if r else "UNAVAILABLE"
            amount = _guest_amount(r) if r and problem is None else None
            out.append(_item_out(None, it.class_id, it.class_month_id, r, amount, problem))
    return _cart(out)


async def _insert(user_id: UUID, it: CartItemIn) -> None:
    async with user_transaction(user_id) as session:
        count = (await session.execute(text("SELECT count(*) FROM cart_items"))).scalar_one()
        exists = (await session.execute(text("""
            SELECT 1 FROM cart_items WHERE class_id = :c AND class_month_id IS NOT DISTINCT FROM CAST(:mo AS uuid)
        """), {"c": it.class_id, "mo": it.class_month_id})).first()
        if exists:
            return
        if count >= MAX_CART_ITEMS:
            raise ApiError("CART_FULL", f"Your cart can hold up to {MAX_CART_ITEMS} items.", status_code=409)
        await session.execute(text("""
            INSERT INTO cart_items (user_id, class_id, class_month_id) VALUES (current_user_id(), :c, :mo)
            ON CONFLICT DO NOTHING
        """), {"c": it.class_id, "mo": it.class_month_id})


async def add_item(user: UserContext, it: CartItemIn) -> Cart:
    async with AppSession() as session:
        r = await _public(session, it.class_id, it.class_month_id)
    if r is None:
        raise ApiError("UNAVAILABLE", "This class isn't available.", status_code=404)
    try:
        async with in_tenant_of("class", it.class_id, user) as (session, auth, _):
            await checkout.price_item(session, auth, it.class_id, it.class_month_id)
    except ApiError as exc:
        # Same message as paying would give (already have it, ask the teacher first, not open yet, ...).
        raise ApiError(exc.code, exc.message, status_code=exc.status_code if exc.status_code != 404 else 409) from exc
    await _insert(user.user_id, it)
    return await get_cart(user)


async def remove_item(user: UserContext, item_id: UUID) -> Cart:
    async with user_transaction(user.user_id) as session:
        await session.execute(text("DELETE FROM cart_items WHERE id = :id"), {"id": item_id})
    return await get_cart(user)


async def merge(user: UserContext, items: list[CartItemIn]) -> Cart:
    """After sign-in: add what the browser held, quietly skipping anything that can't be bought."""
    for it in items[:MAX_CART_ITEMS]:
        async with AppSession() as session:
            r = await _public(session, it.class_id, it.class_month_id)
        if r is None or _public_problem(r, it.class_month_id) in _STRUCTURAL:
            continue
        try:
            await _insert(user.user_id, it)
        except ApiError:
            break                                  # cart full
    return await get_cart(user)


# --- checkout -----------------------------------------------------------------------------

async def _new_checkout_no() -> str:
    return datetime.now(UTC).strftime("EZC-%y%m-") + secrets.token_hex(4).upper()


async def start_checkout(user: UserContext, site_host: str, gateway: Gateway) -> CheckoutStarted:
    s = get_settings()
    rows = await _rows(user.user_id)
    if not rows:
        raise ApiError("CART_EMPTY", "Your cart is empty.", status_code=409)
    async with AppSession() as session:
        await checkout.require_verified_phone(session, user.user_id)

    # 1. Price everything first (read-only, each in its own tenant): nothing is created if any item fails.
    priced: list[checkout.PricedItem] = []
    for row in rows:
        try:
            async with in_tenant_of("class", row.class_id, user) as (session, auth, _):
                priced.append(await checkout.price_item(session, auth, row.class_id, row.class_month_id))
        except ApiError as exc:
            raise ApiError("CART_HAS_PROBLEMS", "Some items in your cart can't be paid for now.", 409) from exc
    if len({p.currency for p in priced}) > 1:
        raise ApiError("CURRENCY_MIXED", "Items in different currencies can't be paid together.", 409)
    total = sum(p.amount_cents for p in priced)
    currency = priced[0].currency

    # 2. The checkout and its one gateway attempt (platform-level, the user's own rows).
    key = secrets.token_hex(16)
    async with user_transaction(user.user_id) as session:
        for _ in range(5):
            try:
                async with session.begin_nested():
                    checkout_id: UUID = (await session.execute(text("""
                        INSERT INTO checkouts (user_id, checkout_no, currency, total_cents)
                        VALUES (current_user_id(), :no, :cur, :total) RETURNING id
                    """), {"no": await _new_checkout_no(), "cur": currency, "total": total})).scalar_one()
                break
            except IntegrityError:
                continue
        else:
            raise ApiError("CHECKOUT_FAILED", "Please try again.", status_code=503)
        cp_id: UUID = (await session.execute(text("""
            INSERT INTO checkout_payments (checkout_id, gateway, idempotency_key, amount_cents)
            VALUES (:c, :g, :k, :amt) RETURNING id
        """), {"c": checkout_id, "g": gateway.name, "k": key, "amt": total})).scalar_one()

    # 3. One pending order per item, each in its own tenant. Prices are checked again inside the transaction
    #    that creates the order; if anything changed meanwhile, the whole checkout is abandoned.
    try:
        for p in priced:
            async with in_tenant_of("class", p.class_id, user) as (session, auth, _):
                auth = await ensure_student_member(session, auth)
                again = await checkout.price_item(session, auth, p.class_id, p.class_month_id)
                if again.amount_cents != p.amount_cents:
                    raise ApiError("CART_CHANGED", "A price in your cart just changed. Please check it again.", 409)
                await checkout.create_order(session, auth, again, gateway=gateway.name,
                                            payment_key=secrets.token_hex(16), checkout_id=checkout_id,
                                            checkout_payment_id=cp_id)
    except ApiError as exc:
        await _close(user.user_id, checkout_id, cp_id, "failed", "could not create every order")
        if exc.code == "CART_CHANGED":
            raise
        raise ApiError("CART_HAS_PROBLEMS", "Some items in your cart can't be paid for now.", 409) from exc

    async with AppSession() as session:
        first, last, email, phone = await checkout.payer(session, user.user_id)
    back = f"{s.site_scheme}://{site_host}/checkouts/{checkout_id}"
    description = priced[0].description if len(priced) == 1 else f"EduZone: {len(priced)} classes"
    redirect = gateway.create_checkout(CheckoutRequest(
        payment_key=key, amount_cents=total, currency=currency, description=description,
        first_name=first, last_name=last, email=email, phone=phone,
        return_url=back, cancel_url=back, notify_url=f"{s.api_public_url}/api/v1/webhooks/{gateway.name}",
    ))
    return CheckoutStarted(checkout=await get_checkout(user.user_id, checkout_id),
                           redirect=Redirect(method=redirect.method, url=redirect.url, fields=redirect.fields))


async def _close(user_id: UUID, checkout_id: UUID, cp_id: UUID, status: str, reason: str | None) -> None:
    async with user_transaction(user_id) as session:
        await session.execute(text("""
            UPDATE checkout_payments SET status = :st, failure_reason = COALESCE(:why, failure_reason)
            WHERE id = :id AND status = 'initiated'
        """), {"st": status, "why": reason, "id": cp_id})
        await session.execute(text("UPDATE checkouts SET status = :st WHERE id = :id AND status = 'pending'"),
                              {"st": status, "id": checkout_id})


async def get_checkout(user_id: UUID, checkout_id: UUID) -> CheckoutDetail:
    """Polled by the return page; only the gateway's notification ever marks anything paid."""
    async with user_transaction(user_id) as session:
        c = (await session.execute(text("""
            SELECT c.id, c.checkout_no, c.status, c.currency, c.total_cents, c.created_at, c.paid_at,
                   cp.status AS payment_status, cp.method, cp.card_last4
            FROM checkouts c
            JOIN LATERAL (SELECT * FROM checkout_payments WHERE checkout_id = c.id
                          ORDER BY created_at DESC LIMIT 1) cp ON true
            WHERE c.id = :id
        """), {"id": checkout_id})).one_or_none()
        if c is None:
            raise ApiError("NOT_FOUND", "Checkout not found.", status_code=404)
        rows = (await session.execute(text("""
            SELECT o.id, o.order_no, o.status, o.currency, o.total_cents, o.created_at, o.paid_at, o.checkout_id,
                   i.id AS item_id, i.class_id, i.class_month_id, i.description, i.amount_cents,
                   t.slug AS org_slug, t.name AS org_name
            FROM orders o
            JOIN order_items i ON i.order_id = o.id
            JOIN tenants t ON t.id = o.tenant_id
            WHERE o.checkout_id = :id
            ORDER BY o.created_at, o.id
        """), {"id": checkout_id})).all()
    return CheckoutDetail(
        id=c.id, checkout_no=c.checkout_no, status=c.status, payment_status=c.payment_status, currency=c.currency,
        total_cents=c.total_cents, created_at=c.created_at, paid_at=c.paid_at, method=c.method,
        card_last4=c.card_last4,
        orders=[OrderOut(
            id=r.id, order_no=r.order_no, status=r.status, currency=r.currency, total_cents=r.total_cents,
            created_at=r.created_at, paid_at=r.paid_at, method=c.method, card_last4=c.card_last4,
            checkout_id=r.checkout_id, org=OrgRef(slug=r.org_slug, name=r.org_name),
            item=OrderItemOut(id=r.item_id, class_id=r.class_id, class_slug=None, class_month_id=r.class_month_id,
                              description=r.description, amount_cents=r.amount_cents),
        ) for r in rows],
    )


# --- the gateway's notification (called by checkout.service.process_notification) -----------

async def apply_checkout_event(event: GatewayEvent, cp_id: UUID, checkout_id: UUID, user_id: UUID) -> str:
    """Record the result on the checkout payment, then settle every order in its own tenant. Safe to repeat:
    a repeat finishes whatever is still pending. Raises if an order could not be fulfilled, so the event stays
    unprocessed and the next delivery retries it."""
    if event.status == "pending":
        return "pending"
    async with user_transaction(user_id) as session:
        cp = (await session.execute(text("""
            SELECT cp.id, cp.status, cp.amount_cents, cp.gateway_fee_cents, c.currency
            FROM checkout_payments cp JOIN checkouts c ON c.id = cp.checkout_id
            WHERE cp.id = :id FOR UPDATE OF cp
        """), {"id": cp_id})).one()
        if event.status == "succeeded":
            if cp.status != "succeeded":
                # The amount and currency must match the checkout exactly.
                if event.amount_cents != cp.amount_cents or event.currency != cp.currency:
                    await session.execute(text(
                        "UPDATE checkout_payments SET failure_reason = 'amount mismatch' WHERE id = :id"), {"id": cp.id})
                    log.warning("checkout payment %s: amount/currency mismatch (%s %s)", cp.id, event.amount_cents,
                                event.currency)
                    return "amount mismatch"
                fee = posting.estimate_fee_cents(cp.amount_cents, get_settings().gateway_fee_estimate_bps)
                await session.execute(text("""
                    UPDATE checkout_payments SET status = 'succeeded', gateway_payment_ref = :ref, method = :method,
                           card_last4 = :last4, gateway_fee_cents = :fee, failure_reason = NULL
                    WHERE id = :id
                """), {"ref": event.gateway_payment_ref, "method": event.method, "last4": event.card_last4,
                       "fee": fee, "id": cp.id})
            else:
                fee = cp.gateway_fee_cents or 0
        elif event.status in ("failed", "cancelled"):
            if cp.status == "succeeded":
                return "ignored: already paid"     # out of order: a late failure never undoes a payment
        else:
            return f"unhandled: {event.status}"
        orders = (await session.execute(text("""
            SELECT o.id AS order_id, o.tenant_id, o.total_cents, p.id AS payment_id
            FROM orders o JOIN payments p ON p.order_id = o.id AND p.checkout_payment_id = :cp
            WHERE o.checkout_id = :c ORDER BY o.created_at, o.id
        """), {"cp": cp_id, "c": checkout_id})).all()

    if event.status in ("failed", "cancelled"):
        for o in orders:
            async with tenant_transaction(o.tenant_id) as session:
                await session.execute(text("""
                    UPDATE payments SET status = :st, failure_reason = :st WHERE id = :id AND status = 'initiated'
                """), {"st": event.status, "id": o.payment_id})
                await session.execute(text("UPDATE orders SET status = :st WHERE id = :id AND status = 'pending'"),
                                      {"st": event.status, "id": o.order_id})
        await _close(user_id, checkout_id, cp_id, event.status, event.status)
        return event.status

    # Succeeded: each order with its share of the fee, in its own tenant. One failure doesn't stop the others.
    shares = posting.allocate(fee, [o.total_cents for o in orders])
    failed: list[UUID] = []
    for o, share in zip(orders, shares, strict=True):
        try:
            async with tenant_transaction(o.tenant_id) as session:
                p = (await session.execute(text("""
                    SELECT p.id, p.status, p.amount_cents, o.id AS order_id, o.status AS order_status, o.total_cents,
                           o.currency, o.student_member_id
                    FROM payments p JOIN orders o ON o.id = p.order_id
                    WHERE p.id = :id FOR UPDATE OF p, o
                """), {"id": o.payment_id})).one()
                if p.status != "succeeded":
                    await checkout.fulfil_order(session, p, event, fee=share, gateway_payment_ref=None)
        except Exception:
            log.exception("checkout %s: order %s could not be fulfilled; will retry", checkout_id, o.order_id)
            failed.append(o.order_id)
    if failed:
        raise RuntimeError(f"{len(failed)} order(s) of checkout {checkout_id} not fulfilled yet")

    paid = [(o.order_id) for o in orders]
    async with user_transaction(user_id) as session:
        await session.execute(text(
            "UPDATE checkouts SET status = 'paid', paid_at = now() WHERE id = :id AND status <> 'paid'"),
            {"id": checkout_id})
        # What was just bought leaves the cart.
        await session.execute(text("""
            DELETE FROM cart_items ci USING order_items i
            WHERE i.order_id = ANY(:orders) AND ci.class_id = i.class_id
              AND ci.class_month_id IS NOT DISTINCT FROM i.class_month_id
        """), {"orders": paid})
    return "paid"
