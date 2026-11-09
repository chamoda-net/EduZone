"""Courses, step C5 (docs/COURSES.md C.7 and C.8): coupons (console rules, typed codes in the cart, public sales,
free checkouts, commission on the amount paid, redemption limits) and the wishlist."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlparse
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AppSession
from app.core.tenancy import tenant_transaction
from tests.conftest import FakeSms, Seed
from tests.helpers import error_code
from tests.test_cart import pay
from tests.test_courses import O, teacher  # noqa: F401  (fixtures)
from tests.test_learn import main_login
from tests.test_market_courses import live_course
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
Phones = Callable[[], str]
CART = "/api/v1/me/cart"
M = "/api/v1/market"


@pytest.fixture
async def course(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers) -> dict[str, Any]:  # noqa: F811
    """A paid course (Rs. 3,000) on the marketplace."""
    return await live_course(client, seed, teacher, ph, f"Firewalls {uuid4().hex[:6]}")


@pytest.fixture
async def student(client: AsyncClient, sms: FakeSms, phones: Phones) -> Headers:
    return await main_login(client, sms, phones())


def code() -> str:
    return "C5-" + uuid4().hex[:8].upper()


async def coupon(client: AsyncClient, h: Headers, course_id: str | None, **kw: Any) -> dict[str, Any]:
    body = {"code": code(), "course_id": course_id, "discount_type": "percent", "percent_bps": 2000,
            "ends_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(), **kw}
    r = await client.post(f"{O}/coupons", headers=h, json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def ledger(tenant_id: UUID, course_id: str) -> dict[str, int]:
    async with tenant_transaction(tenant_id) as s:
        rows = (await s.execute(text("""
            SELECT le.account, sum(le.amount_cents) AS amount
            FROM ledger_entries le JOIN order_items i ON i.id = le.order_item_id
            WHERE i.class_id = :c GROUP BY le.account
        """), {"c": course_id})).all()
    return {r.account: int(r.amount) for r in rows}


async def redeemed(tenant_id: UUID, coupon_id: str) -> int:
    async with tenant_transaction(tenant_id) as s:
        return (await s.execute(text("SELECT redeemed_count FROM coupons WHERE id = :id"),
                                {"id": coupon_id})).scalar_one()


# --- console ------------------------------------------------------------------------------------

async def test_console_rules(client: AsyncClient, seed: Seed, teacher: Headers,  # noqa: F811
                             course: dict[str, Any]) -> None:
    cid = course["id"]
    made = await coupon(client, teacher, cid, code="launch-20")
    assert made["code"] == "LAUNCH-20" and made["state"] == "active" and made["course_title"] == course["title"]
    assert made["redeemed_count"] == 0 and made["is_public"] is False

    later = (datetime.now(UTC) + timedelta(days=30)).isoformat()

    async def refused(status: int, err: str | None, **body: Any) -> None:
        r = await client.post(f"{O}/coupons", headers=teacher, json={
            "code": code(), "course_id": cid, "discount_type": "percent", "percent_bps": 1000, "ends_at": later,
            **body})
        assert r.status_code == status, r.text
        if err:
            assert error_code(r) == err

    await refused(409, "COUPON_CODE_TAKEN", code="LAUNCH-20")
    await refused(422, "COUPON_TOO_LONG", ends_at=(datetime.now(UTC) + timedelta(days=91)).isoformat())
    await refused(422, "COUPON_DATES", ends_at=(datetime.now(UTC) - timedelta(days=1)).isoformat())
    await refused(422, "COUPON_VALUE_INVALID", discount_type="fixed")                   # a percent with a fixed type
    await refused(422, None, code="no")                                           # 4-20 letters, digits, dashes
    await refused(403, "ACCESS_DENIED", course_id=None)                           # a teacher: own courses only
    await refused(404, "NOT_FOUND", course_id=str(uuid4()))

    off = await client.patch(f"{O}/coupons/{made['id']}", headers=teacher, json={"status": "disabled"})
    assert off.json()["state"] == "disabled"
    rows = (await client.get(f"{O}/coupons", headers=teacher)).json()
    assert made["id"] in {r["id"] for r in rows}
    # Another organization never sees it.
    async with tenant_transaction(seed.b.id) as s:
        assert (await s.execute(text("SELECT count(*) FROM coupons WHERE id = :id"), {"id": made["id"]})).scalar_one() == 0


# --- typed codes in the cart -------------------------------------------------------------------------

async def test_code_in_cart_and_commission_on_amount_paid(client: AsyncClient, seed: Seed, teacher: Headers,  # noqa: F811
                                                          course: dict[str, Any], student: Headers) -> None:
    cid = course["id"]
    k = await coupon(client, teacher, cid, max_redemptions=1)
    assert (await client.post(f"{CART}/items", headers=student, json={"class_id": cid})).status_code == 201
    bad = await client.post(f"{CART}/coupon", headers=student, json={"code": "NOPE-1234"})
    assert bad.status_code == 404 and error_code(bad) == "COUPON_INVALID"

    cart = (await client.post(f"{CART}/coupon", headers=student, json={"code": k["code"].lower()})).json()
    item = cart["items"][0]
    assert (item["list_price_cents"], item["discount_cents"], item["amount_cents"]) == (300000, 60000, 240000)
    assert item["coupon_code"] == k["code"] and not item["coupon_public"] and cart["codes"] == [k["code"]]
    assert (cart["subtotal_cents"], cart["discount_cents"], cart["total_cents"]) == (300000, 60000, 240000)

    removed = (await client.delete(f"{CART}/coupon/{k['code']}", headers=student)).json()
    assert removed["total_cents"] == 300000 and removed["codes"] == []
    await client.post(f"{CART}/coupon", headers=student, json={"code": k["code"]})

    out, form = await pay(client, student, amount=240000)
    assert out["checkout"]["total_cents"] == 240000
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "paid"

    # The order keeps the list price, the discount and the coupon; commission is on the amount paid.
    async with tenant_transaction(seed.a.id) as s:
        oi = (await s.execute(text("""
            SELECT i.amount_cents, i.list_price_cents, i.discount_cents, i.coupon_id, o.subtotal_cents, o.discount_cents
                   AS order_discount, o.total_cents
            FROM order_items i JOIN orders o ON o.id = i.order_id WHERE i.class_id = :c AND o.status = 'paid'
        """), {"c": cid})).one()
    assert (oi.amount_cents, oi.list_price_cents, oi.discount_cents, str(oi.coupon_id)) == (240000, 300000, 60000,
                                                                                            k["id"])
    assert (oi.subtotal_cents, oi.order_discount, oi.total_cents) == (300000, 60000, 240000)
    books = await ledger(seed.a.id, cid)
    assert books["platform_commission"] == -48000                     # 20% of 240000
    assert sum(books.values()) == 0
    assert await redeemed(seed.a.id, k["id"]) == 1

    # Used up: the code no longer applies for anyone.
    assert (await client.get(f"{O}/coupons", headers=teacher)).json()[0]["state"] == "used_up"


async def test_used_up_code_is_refused(client: AsyncClient, seed: Seed, teacher: Headers,  # noqa: F811
                                       course: dict[str, Any], student: Headers) -> None:
    k = await coupon(client, teacher, course["id"], max_redemptions=1)
    async with tenant_transaction(seed.a.id) as s:
        await s.execute(text("UPDATE coupons SET redeemed_count = 1 WHERE id = :id"), {"id": k["id"]})
    await client.post(f"{CART}/items", headers=student, json={"class_id": course["id"]})
    r = await client.post(f"{CART}/coupon", headers=student, json={"code": k["code"]})
    assert r.status_code == 404 and error_code(r) == "COUPON_INVALID"


# --- public sales and the course page ------------------------------------------------------------------

async def test_public_sale_and_best_discount(client: AsyncClient, seed: Seed, teacher: Headers,  # noqa: F811
                                             course: dict[str, Any], student: Headers) -> None:
    cid, slug = course["id"], course["slug"]
    sale = await coupon(client, teacher, cid, is_public=True, percent_bps=1000)              # 10% for everyone
    card = (await client.get(f"{M}/course/{slug}")).json()["course"]
    assert card["sale_price_cents"] == 270000 and card["sale_ends_at"]
    assert slug in {c["slug"] for c in (await client.get(f"{M}/courses", params={"max_price": 270000})).json()["items"]}

    # A guest's cart and a signed-in cart both get the sale without a code.
    guest = (await client.post(f"{M}/cart/preview", json={"items": [{"class_id": cid}]})).json()
    assert guest["items"][0]["amount_cents"] == 270000 and guest["items"][0]["coupon_public"]
    await client.post(f"{CART}/items", headers=student, json={"class_id": cid})
    cart = (await client.get(CART, headers=student)).json()
    assert cart["total_cents"] == 270000 and cart["codes"] == []

    # A better typed code wins (no stacking); a worse one changes nothing.
    better = await coupon(client, teacher, cid, discount_type="fixed", percent_bps=None, amount_cents=100000)
    worse = await coupon(client, teacher, cid, percent_bps=500)
    cart = (await client.post(f"{CART}/coupon", headers=student, json={"code": worse["code"]})).json()
    assert cart["total_cents"] == 270000 and cart["items"][0]["coupon_code"] == sale["code"]
    cart = (await client.post(f"{CART}/coupon", headers=student, json={"code": better["code"]})).json()
    assert cart["total_cents"] == 200000 and cart["items"][0]["coupon_code"] == better["code"]

    # The course page with ?coupon= (a teacher's shared link).
    quote = (await client.get(f"{M}/course/{slug}", params={"coupon": better["code"].lower()})).json()["coupon"]
    assert quote["valid"] and quote["applied"] and quote["price_cents"] == 200000 and quote["discount_cents"] == 100000
    quote = (await client.get(f"{M}/course/{slug}", params={"coupon": worse["code"]})).json()["coupon"]
    assert quote["valid"] and not quote["applied"] and quote["price_cents"] == 270000
    quote = (await client.get(f"{M}/course/{slug}", params={"coupon": "NOPE-0000"})).json()["coupon"]
    assert not quote["valid"]
    # A disabled sale disappears from the card.
    await client.patch(f"{O}/coupons/{sale['id']}", headers=teacher, json={"status": "disabled"})
    assert (await client.get(f"{M}/course/{slug}")).json()["course"]["sale_price_cents"] is None


async def test_code_from_link_when_adding(client: AsyncClient, teacher: Headers,  # noqa: F811
                                          course: dict[str, Any], student: Headers) -> None:
    k = await coupon(client, teacher, course["id"], percent_bps=5000)
    bad = await client.post(f"{CART}/items", headers=student, json={"class_id": course["id"], "coupon_code": "XXXX-9"})
    assert bad.status_code == 201 and bad.json()["total_cents"] == 300000                # ignored, not an error
    good = await client.post(f"{CART}/items", headers=student, json={"class_id": course["id"], "coupon_code": k["code"]})
    assert good.json()["total_cents"] == 150000 and good.json()["codes"] == [k["code"]]


# --- a coupon that makes the course free ---------------------------------------------------------------

async def test_free_checkout(client: AsyncClient, seed: Seed, teacher: Headers,  # noqa: F811
                             course: dict[str, Any], student: Headers) -> None:
    cid = course["id"]
    k = await coupon(client, teacher, cid, percent_bps=10000)
    await client.post(f"{CART}/items", headers=student, json={"class_id": cid, "coupon_code": k["code"]})
    started = await client.post("/api/v1/me/checkouts", headers=student)
    assert started.status_code == 201, started.text
    out = started.json()
    # No gateway: straight to the return page, already paid.
    assert out["redirect"]["method"] == "GET" and urlparse(out["redirect"]["url"]).path.startswith("/checkouts/")
    assert out["checkout"]["status"] == "paid" and out["checkout"]["total_cents"] == 0
    view = (await client.get(f"/api/v1/learn/courses/{cid}", headers=student)).json()
    assert view["has_access"]
    assert (await client.get(CART, headers=student)).json()["items"] == []
    # No money moved: nothing is booked. The coupon is counted.
    assert await ledger(seed.a.id, cid) == {}
    assert await redeemed(seed.a.id, k["id"]) == 1


# --- the wishlist -------------------------------------------------------------------------------------

async def test_wishlist(client: AsyncClient, seed: Seed, teacher: Headers, course: dict[str, Any],  # noqa: F811
                        student: Headers, sms: FakeSms, phones: Phones) -> None:
    cid = course["id"]
    W = "/api/v1/me/wishlist"
    assert (await client.put(f"{W}/{cid}", headers=student)).json() == [cid]
    assert (await client.put(f"{W}/{cid}", headers=student)).json() == [cid]           # idempotent
    assert (await client.put(f"{W}/{uuid4()}", headers=student)).status_code == 404
    listed = (await client.get(W, headers=student)).json()
    assert [c["id"] for c in listed] == [cid] and listed[0]["path"] == f"/course/{course['slug']}"
    assert (await client.get(f"{O}/courses/{cid}", headers=teacher)).json()["wishlist_count"] == 1

    # Private to the student.
    other = await main_login(client, sms, phones())
    assert (await client.get(f"{W}/ids", headers=other)).json() == []
    async with AppSession() as s:
        assert (await s.execute(text("SELECT count(*) FROM wishlist_items"))).scalar_one() == 0

    assert (await client.delete(f"{W}/{cid}", headers=student)).json() == []
    await client.put(f"{W}/{cid}", headers=student)

    # Buying it takes it off the wishlist.
    await client.post(f"{CART}/items", headers=student, json={"class_id": cid})
    _, form = await pay(client, student, amount=300000)
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "paid"
    assert (await client.get(f"{W}/ids", headers=student)).json() == []
