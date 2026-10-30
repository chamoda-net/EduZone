"""Phase 6: the cart and one payment across teachers. Pricing by the same rules as Pay, one checkout payment,
one order per item in its own tenant, the gateway fee split exactly, idempotent and retried fulfilment."""

from collections.abc import Callable
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction, user_transaction
from app.modules.checkout import service as checkout_service
from app.modules.ledger.posting import allocate
from tests.conftest import FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_checkout import fake, ledger, payment_key
from tests.test_learn import main_login, user_id_of
from tests.test_market import physics_id, published

Headers = dict[str, str]
Phones = Callable[[], str]


# --- the fee split ----------------------------------------------------------------------------

@pytest.mark.parametrize(("total", "weights"), [
    (10500, [200000, 150000]), (10, [1, 1, 1]), (1, [3, 3]), (0, [5, 7]), (9999, [1, 2, 3, 4, 5, 6, 7]),
])
def test_allocate_sums_exactly(total: int, weights: list[int]) -> None:
    shares = allocate(total, weights)
    assert sum(shares) == total and all(s >= 0 for s in shares)
    # Each share is within one cent of its exact proportion.
    for s, w in zip(shares, weights, strict=True):
        assert abs(s - total * w / sum(weights)) < 1


def test_allocate_ties_go_to_the_first() -> None:
    assert allocate(10, [1, 1, 1]) == [4, 3, 3]
    assert allocate(6000, [200000, 100000]) == [4000, 2000]
    with pytest.raises(ValueError):
        allocate(5, [0, 0])


# --- fixtures -----------------------------------------------------------------------------------

async def one_time_class(client: AsyncClient, teacher: Headers, price: int = 150000) -> dict[str, Any]:
    c = (await client.post("/api/v1/org/classes", headers=teacher, json={
        "title": "Organic Chemistry Crash Course", "pricing_model": "one_time", "one_time_price_cents": price,
        "subject_id": await physics_id()})).json()
    assert (await client.patch(f"/api/v1/org/classes/{c['id']}", headers=teacher,
                               json={"status": "published"})).status_code == 200
    return c


@pytest.fixture
async def shop(client: AsyncClient, sms: FakeSms, seed: Seed, phones: Phones) -> dict[str, Any]:
    """A monthly class at tenant A, a one-time class at tenant B, and a fresh student on the main host."""
    teacher_a = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    teacher_b = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    monthly = await published(client, teacher_a)
    once = await one_time_class(client, teacher_b)
    phone = phones()
    return {"a": monthly, "b": once, "student": await main_login(client, sms, phone), "phone": phone,
            "teacher_a": teacher_a}


async def add(client: AsyncClient, h: Headers, class_id: str, month_id: str | None = None) -> Any:
    body: dict[str, Any] = {"class_id": class_id}
    if month_id:
        body["class_month_id"] = month_id
    return await client.post("/api/v1/me/cart/items", headers=h, json=body)


async def fill(client: AsyncClient, shop: dict[str, Any]) -> None:
    h = shop["student"]
    assert (await add(client, h, shop["a"]["class"]["id"], shop["a"]["months"]["open"]["id"])).status_code == 201
    assert (await add(client, h, shop["b"]["id"])).status_code == 201


async def pay(client: AsyncClient, h: Headers, status: str = "succeeded", amount: int = 350000) -> tuple[Any, Any]:
    started = await client.post("/api/v1/me/checkouts", headers=h)
    assert started.status_code == 201, started.text
    out = started.json()
    form = fake().notification(payment_key(out), status, amount, "LKR")  # type: ignore[arg-type]
    return out, form


async def fees(tenant_id: UUID) -> list[int]:
    async with tenant_transaction(tenant_id) as s:
        return list((await s.execute(text(
            "SELECT gateway_fee_cents FROM payments WHERE checkout_payment_id IS NOT NULL AND status = 'succeeded'"
        ))).scalars())


# --- the happy path -------------------------------------------------------------------------------

async def test_two_teachers_one_payment(client: AsyncClient, seed: Seed, shop: dict[str, Any]) -> None:
    h = shop["student"]
    await fill(client, shop)
    cart = (await client.get("/api/v1/me/cart", headers=h)).json()
    assert cart["ready"] and cart["total_cents"] == 350000 and len(cart["items"]) == 2
    assert {i["org"]["slug"] for i in cart["items"]} == {seed.a.slug, seed.b.slug}
    assert (await client.get("/api/v1/auth/me", headers=h)).json()["cart_count"] == 2

    out, form = await pay(client, h)
    detail = out["checkout"]
    assert detail["status"] == "pending" and detail["total_cents"] == 350000 and len(detail["orders"]) == 2
    assert {o["status"] for o in detail["orders"]} == {"pending"}
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "paid"

    paid = (await client.get(f"/api/v1/me/checkouts/{detail['id']}", headers=h)).json()
    assert paid["status"] == "paid" and paid["payment_status"] == "succeeded" and paid["card_last4"] == "4242"
    assert {o["status"] for o in paid["orders"]} == {"paid"}
    # One sale per tenant, balanced; the 3% fee estimate (10500) is split 6000 / 4500 and adds up exactly.
    for tenant, fee in ((seed.a.id, 6000), (seed.b.id, 4500)):
        assert (await ledger(tenant))["sales"] == 1 and (await ledger(tenant))["unbalanced"] == 0
        assert await fees(tenant) == [fee]
    # The cart is empty and the orders show in the payment history (access: next test).
    assert (await client.get("/api/v1/me/cart", headers=h)).json()["items"] == []
    history = (await client.get("/api/v1/learn/payments", headers=h)).json()
    assert {o["checkout_id"] for o in history} == {detail["id"]}

    # The same notification again, and a second notification of the same success: nothing more is booked.
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "duplicate"
    again = fake().notification(payment_key(out), "succeeded", 350000, "LKR")  # type: ignore[arg-type]
    assert (await client.post("/api/v1/webhooks/fake", data=again)).json()["outcome"] == "paid"
    for tenant in (seed.a.id, seed.b.id):
        assert (await ledger(tenant))["sales"] == 1
    # A late failure never undoes it.
    late = fake().notification(payment_key(out), "failed", 350000, "LKR")  # type: ignore[arg-type]
    assert (await client.post("/api/v1/webhooks/fake", data=late)).json()["outcome"] == "ignored: already paid"


async def test_access_after_cart_payment(client: AsyncClient, seed: Seed, shop: dict[str, Any]) -> None:
    h = shop["student"]
    await fill(client, shop)
    out, form = await pay(client, h)
    await client.post("/api/v1/webhooks/fake", data=form)
    async with tenant_transaction(seed.a.id) as s:
        a = (await s.execute(text("SELECT count(*) FROM access_grants WHERE source = 'purchase' AND class_month_id = :m"),
                             {"m": shop["a"]["months"]["open"]["id"]})).scalar_one()
    async with tenant_transaction(seed.b.id) as s:
        b = (await s.execute(text("SELECT count(*) FROM access_grants WHERE source = 'purchase' AND class_id = :c"),
                             {"c": shop["b"]["id"]})).scalar_one()
    assert (a, b) == (1, 1)
    # Bought: it can't go back in the cart.
    back = await add(client, h, shop["b"]["id"])
    assert back.status_code == 409 and error_code(back) == "ALREADY_HAS_ACCESS"


# --- rules ---------------------------------------------------------------------------------------

async def test_cart_rules(client: AsyncClient, seed: Seed, shop: dict[str, Any], sms: FakeSms, phones: Phones) -> None:
    h, a = shop["student"], shop["a"]
    closed = await add(client, h, a["class"]["id"], a["months"]["closed"]["id"])
    assert closed.status_code == 409 and error_code(closed) == "LATE_APPROVAL_REQUIRED"
    upcoming = await add(client, h, a["class"]["id"], a["months"]["upcoming"]["id"])
    assert upcoming.status_code == 409 and error_code(upcoming) == "MONTH_NOT_OPEN"
    no_month = await add(client, h, a["class"]["id"])
    assert no_month.status_code in (400, 409) and error_code(no_month) == "MONTH_REQUIRED"
    assert (await add(client, h, "00000000-0000-0000-0000-000000000000")).status_code == 404

    await fill(client, shop)
    await fill(client, shop)                                     # adding twice keeps one of each
    cart = (await client.get("/api/v1/me/cart", headers=h)).json()
    assert len(cart["items"]) == 2
    one = next(i for i in cart["items"] if i["class_id"] == shop["b"]["id"])
    left = (await client.delete(f"/api/v1/me/cart/items/{one['id']}", headers=h)).json()
    assert len(left["items"]) == 1 and left["total_cents"] == 200000

    # A guest's cart (from the browser) is priced from public data; a closed month shows why it can't be paid.
    preview = (await client.post("/api/v1/market/cart/preview", json={"items": [
        {"class_id": shop["b"]["id"]},
        {"class_id": a["class"]["id"], "class_month_id": a["months"]["closed"]["id"]}]})).json()
    assert [i["problem"] for i in preview["items"]] == [None, "LATE_APPROVAL_REQUIRED"]
    assert preview["total_cents"] == 150000 and not preview["ready"]

    # After sign-in the browser's items join the account's cart; impossible ones are skipped quietly.
    merged = (await client.post("/api/v1/me/cart/merge", headers=h, json={"items": [
        {"class_id": shop["b"]["id"]}, {"class_id": a["class"]["id"]}]})).json()
    assert len(merged["items"]) == 2

    # Someone else's cart is not ours: another student sees nothing and can't delete our items.
    other = await main_login(client, sms, phones())
    assert (await client.get("/api/v1/me/cart", headers=other)).json()["items"] == []
    await client.delete(f"/api/v1/me/cart/items/{merged['items'][0]['id']}", headers=other)
    assert len((await client.get("/api/v1/me/cart", headers=h)).json()["items"]) == 2
    assert error_code(await client.post("/api/v1/me/checkouts", headers=other)) == "CART_EMPTY"


async def test_checkout_refuses_problems_and_unverified_phones(client: AsyncClient, seed: Seed,
                                                                 shop: dict[str, Any]) -> None:
    h = shop["student"]
    await fill(client, shop)
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE users SET phone_verified_at = NULL WHERE phone = :p"), {"p": shop["phone"]})
    unverified = await client.post("/api/v1/me/checkouts", headers=h)
    assert unverified.status_code == 403 and error_code(unverified) == "PHONE_NOT_VERIFIED"
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE users SET phone_verified_at = now() WHERE phone = :p"), {"p": shop["phone"]})

    # The teacher closes the month after it went in the cart: it now needs approval, so nothing is created.
    await client.patch(f"/api/v1/org/months/{shop['a']['months']['open']['id']}", headers=shop["teacher_a"],
                       json={"status": "closed"})
    cart = (await client.get("/api/v1/me/cart", headers=h)).json()
    assert not cart["ready"] and {i["problem"] for i in cart["items"]} == {None, "LATE_APPROVAL_REQUIRED"}
    refused = await client.post("/api/v1/me/checkouts", headers=h)
    assert refused.status_code == 409 and error_code(refused) == "CART_HAS_PROBLEMS"
    async with user_transaction(await user_id_of(shop["phone"])) as s:
        assert (await s.execute(text("SELECT count(*) FROM checkouts"))).scalar_one() == 0


# --- failures --------------------------------------------------------------------------------------

async def test_declined_payment(client: AsyncClient, seed: Seed, shop: dict[str, Any]) -> None:
    h = shop["student"]
    await fill(client, shop)
    out, form = await pay(client, h, status="failed")
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "failed"
    detail = (await client.get(f"/api/v1/me/checkouts/{out['checkout']['id']}", headers=h)).json()
    assert detail["status"] == "failed" and {o["status"] for o in detail["orders"]} == {"failed"}
    assert len((await client.get("/api/v1/me/cart", headers=h)).json()["items"]) == 2   # the cart stays
    assert (await ledger(seed.a.id))["sales"] == 0


async def test_amount_mismatch_books_nothing(client: AsyncClient, seed: Seed, shop: dict[str, Any]) -> None:
    await fill(client, shop)
    out, form = await pay(client, shop["student"], amount=200000)
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "amount mismatch"
    assert (await ledger(seed.a.id))["sales"] == 0 and (await ledger(seed.b.id))["sales"] == 0


async def test_one_tenant_failing_is_retried(client: AsyncClient, seed: Seed, shop: dict[str, Any],
                                             monkeypatch: pytest.MonkeyPatch) -> None:
    h = shop["student"]
    await fill(client, shop)
    out, form = await pay(client, h)

    real = checkout_service.fulfil_order

    async def broken_in_b(session: Any, p: Any, event: Any, **kw: Any) -> None:
        tenant = (await session.execute(text("SELECT current_tenant_id()"))).scalar_one()
        if tenant == seed.b.id:
            raise RuntimeError("database hiccup")
        await real(session, p, event, **kw)

    monkeypatch.setattr(checkout_service, "fulfil_order", broken_in_b)
    with pytest.raises(RuntimeError):
        await checkout_service.process_notification("fake", form)
    detail = (await client.get(f"/api/v1/me/checkouts/{out['checkout']['id']}", headers=h)).json()
    assert detail["status"] == "pending" and detail["payment_status"] == "succeeded"
    assert sorted(o["status"] for o in detail["orders"]) == ["paid", "pending"]   # A done, B waiting

    # The gateway delivers the same notification again: B is fulfilled, A is not booked twice.
    monkeypatch.setattr(checkout_service, "fulfil_order", real)
    assert await checkout_service.process_notification("fake", form) == "paid"
    detail = (await client.get(f"/api/v1/me/checkouts/{out['checkout']['id']}", headers=h)).json()
    assert detail["status"] == "paid" and {o["status"] for o in detail["orders"]} == {"paid"}
    for tenant in (seed.a.id, seed.b.id):
        assert (await ledger(tenant))["sales"] == 1
    assert sum(await fees(seed.a.id) + await fees(seed.b.id)) == 10500


async def test_checkouts_are_private(client: AsyncClient, shop: dict[str, Any], sms: FakeSms, phones: Phones) -> None:
    await fill(client, shop)
    out, _ = await pay(client, shop["student"])
    other = await main_login(client, sms, phones())
    assert (await client.get(f"/api/v1/me/checkouts/{out['checkout']['id']}", headers=other)).status_code == 404
    async with user_transaction(await user_id_of(shop["phone"])) as s:
        assert (await s.execute(text("SELECT count(*) FROM checkout_payments"))).scalar_one() == 1
    # The app role with no user sees no checkouts at all.
    async with tenant_transaction(UUID(int=0)) as s:
        assert (await s.execute(text("SELECT count(*) FROM checkouts"))).scalar_one() == 0
        assert (await s.execute(text("SELECT count(*) FROM cart_items"))).scalar_one() == 0
