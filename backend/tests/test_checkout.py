"""Step 7: checkout, the gateway webhook (idempotency, signature, amount checks, ordering),
fulfilment in one transaction, and ledger postings."""

import hashlib
from typing import Any
from urllib.parse import urlparse

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from app.integrations.gateways import get_gateway
from app.integrations.gateways.base import CheckoutRequest, parse_amount_cents
from app.integrations.gateways.fake import FakeGateway
from app.integrations.gateways.payhere import PayHereGateway
from app.modules.checkout.service import settle_fee
from tests.conftest import AddMember, FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_learning import member_id, monthly_class

Headers = dict[str, str]


@pytest.fixture
async def teacher(client: AsyncClient, sms: FakeSms, seed: Seed) -> Headers:
    return await auth_headers(client, sms, seed.a, seed.a.teacher_phone)


@pytest.fixture
async def student(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember) -> Headers:
    return await auth_headers(client, sms, seed.a, await members(seed.a, "student"))


async def checkout(client: AsyncClient, h: Headers, class_id: str, month_id: str | None = None) -> Response:
    body: dict[str, Any] = {"class_id": class_id}
    if month_id:
        body["class_month_id"] = month_id
    return await client.post("/api/v1/student/checkout", headers=h, json=body)


def payment_key(out: dict[str, Any]) -> str:
    return urlparse(out["redirect"]["url"]).path.rsplit("/", 1)[-1]


def fake() -> FakeGateway:
    gw = get_gateway("fake")
    assert isinstance(gw, FakeGateway)
    return gw


async def notify(client: AsyncClient, key: str, status: str = "succeeded", amount: int = 200000,
                 currency: str = "LKR", **override: str) -> Response:
    form = fake().notification(key, status, amount, currency)  # type: ignore[arg-type]
    form.update(override)
    return await client.post("/api/v1/webhooks/fake", data=form)


async def ledger(tenant_id: Any) -> dict[str, Any]:
    async with tenant_transaction(tenant_id) as s:
        tx = (await s.execute(text("SELECT count(*) FROM ledger_transactions WHERE kind = 'sale'"))).scalar_one()
        bal = (await s.execute(text("SELECT balance_due_cents FROM v_tenant_balance"))).scalar_one_or_none()
        unbalanced = (await s.execute(text("""
            SELECT count(*) FROM (SELECT ledger_tx_id FROM ledger_entries GROUP BY 1 HAVING sum(amount_cents) <> 0) x
        """))).scalar_one()
    return {"sales": tx, "balance": bal, "unbalanced": unbalanced}


# --- gateways -------------------------------------------------------------------------------

def test_parse_amount() -> None:
    assert parse_amount_cents("2000.00") == 200000
    assert parse_amount_cents("2000.5") == 200050
    assert parse_amount_cents("7") == 700
    for bad in (None, "", "-1.00", "1.234", "1e3", "abc"):
        assert parse_amount_cents(bad) is None


def test_payhere_hashes() -> None:
    gw = PayHereGateway("1211149", "secret", sandbox=True)
    secret_md5 = hashlib.md5(b"secret").hexdigest().upper()
    redirect = gw.create_checkout(CheckoutRequest(
        payment_key="abc", amount_cents=200000, currency="LKR", description="Physics - October 2026",
        first_name="Nimal", last_name="Perera", email="", phone="+94771234567",
        return_url="https://x/r", cancel_url="https://x/c", notify_url="https://api/n"))
    assert redirect.method == "POST" and redirect.url == "https://sandbox.payhere.lk/pay/checkout"
    expected = hashlib.md5(f"1211149abc2000.00LKR{secret_md5}".encode()).hexdigest().upper()
    assert redirect.fields["hash"] == expected and redirect.fields["amount"] == "2000.00"

    form = {"merchant_id": "1211149", "order_id": "abc", "payment_id": "320025", "payhere_amount": "2000.00",
            "payhere_currency": "LKR", "status_code": "2", "method": "VISA", "card_no": "************1292"}
    form["md5sig"] = hashlib.md5(f"1211149abc2000.00LKR2{secret_md5}".encode()).hexdigest().upper()
    event = gw.verify_webhook(form)
    assert event.signature_ok and event.status == "succeeded" and event.amount_cents == 200000
    assert (event.card_last4, event.method, event.payment_key) == ("1292", "visa", "abc")
    assert not gw.verify_webhook({**form, "payhere_amount": "20.00"}).signature_ok
    assert not gw.verify_webhook({**form, "merchant_id": "999"}).signature_ok


# --- checkout rules ---------------------------------------------------------------------------

async def test_checkout_creates_pending_order(client: AsyncClient, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    resp = await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])
    assert resp.status_code == 201, resp.text
    out = resp.json()
    assert out["order"]["status"] == "pending" and out["order"]["total_cents"] == 200000
    assert out["order"]["order_no"].startswith("EZ-")
    assert out["order"]["item"]["description"] == "A/L Physics - November 2026"
    assert out["redirect"]["method"] == "GET" and "/api/v1/dev/fake-gateway/" in out["redirect"]["url"]
    view = (await client.get(f"/api/v1/student/classes/{k['class']['slug']}", headers=student)).json()
    assert view["enrolled"] is True                              # paying implies joining
    assert {m["month_start"]: m["access"] for m in view["months"]}["2026-11-01"] == "buy"   # not yet paid


async def test_checkout_rules(client: AsyncClient, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    cid = k["class"]["id"]
    assert error_code(await checkout(client, student, cid)) == "MONTH_REQUIRED"
    assert error_code(await checkout(client, student, cid, k["months"]["upcoming"]["id"])) == "MONTH_NOT_OPEN"
    assert error_code(await checkout(client, student, cid, k["months"]["closed"]["id"])) == "LATE_APPROVAL_REQUIRED"
    free = (await client.post("/api/v1/org/classes", headers=teacher, json={"title": "Free", "pricing_model": "free"})).json()
    await client.patch(f"/api/v1/org/classes/{free['id']}", headers=teacher, json={"status": "published"})
    assert error_code(await checkout(client, student, free["id"])) == "FREE_CLASS"
    draft = (await client.post("/api/v1/org/classes", headers=teacher, json={
        "title": "Draft", "pricing_model": "one_time", "one_time_price_cents": 500000})).json()
    assert (await checkout(client, student, draft["id"])).status_code == 404

    sid = await member_id(client, student)
    await client.post(f"/api/v1/org/classes/{cid}/grants", headers=teacher,
                      json={"student_member_id": sid, "class_month_id": k["months"]["open"]["id"]})
    assert error_code(await checkout(client, student, cid, k["months"]["open"]["id"])) == "ALREADY_HAS_ACCESS"


# --- the webhook --------------------------------------------------------------------------------

async def test_payment_unlocks_and_books_once(client: AsyncClient, seed: Seed, teacher: Headers,
                                              student: Headers) -> None:
    k = await monthly_class(client, teacher)
    out = (await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])).json()
    key = payment_key(out)

    # Webhooks arrive without a tenant host.
    resp = await notify(client, key)
    assert resp.json() == {"ok": True, "outcome": "paid"}
    order = (await client.get(f"/api/v1/student/orders/{out['order']['id']}", headers=student)).json()
    assert order["status"] == "paid" and order["paid_at"] and order["card_last4"] == "4242"
    lesson = (await client.get(f"/api/v1/student/lessons/{k['lessons']['open']['id']}", headers=student)).json()
    assert lesson["unlocked"] is True and lesson["zoom_join_url"]

    # Default estimate 3% fee, borne by the tenant; 20% commission: 200000 - 40000 - 6000.
    assert await ledger(seed.a.id) == {"sales": 1, "balance": 154000, "unbalanced": 0}

    # The same notification again, and a second "succeeded" event: nothing more is booked.
    form = fake().notification(key, "succeeded", 200000, "LKR")
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "duplicate"  # new event
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "duplicate"  # stored one
    assert await ledger(seed.a.id) == {"sales": 1, "balance": 154000, "unbalanced": 0}
    async with AdminSession() as s:
        grants = (await s.execute(text("SELECT count(*) FROM access_grants WHERE tenant_id = :t AND source = 'purchase'"),
                                  {"t": seed.a.id})).scalar_one()
    assert grants == 1

    # A late failure never undoes a payment.
    assert (await notify(client, key, status="failed")).json()["outcome"] == "ignored: already paid"
    order = (await client.get(f"/api/v1/student/orders/{out['order']['id']}", headers=student)).json()
    assert order["status"] == "paid"

    # Teacher's payments list.
    rows = (await client.get("/api/v1/org/orders", headers=teacher)).json()["items"]
    assert [(r["order_no"], r["status"]) for r in rows] == [(order["order_no"], "paid")]


async def test_bad_signature_is_rejected(client: AsyncClient, seed: Seed, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    out = (await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])).json()
    resp = await notify(client, payment_key(out), sig="0" * 64)
    assert resp.status_code == 400
    order = (await client.get(f"/api/v1/student/orders/{out['order']['id']}", headers=student)).json()
    assert order["status"] == "pending"
    async with AdminSession() as s:
        stored = (await s.execute(text("""
            SELECT signature_ok, process_error FROM gateway_webhook_events WHERE payload->>'order_id' = :k
        """), {"k": payment_key(out)})).one()
    assert stored.signature_ok is False and stored.process_error == "invalid signature"  # stored before rejecting


async def test_amount_must_match(client: AsyncClient, seed: Seed, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    out = (await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])).json()
    assert (await notify(client, payment_key(out), amount=100)).json()["outcome"] == "amount mismatch"
    assert (await notify(client, payment_key(out), currency="USD")).json()["outcome"] == "amount mismatch"
    order = (await client.get(f"/api/v1/student/orders/{out['order']['id']}", headers=student)).json()
    assert order["status"] == "pending"
    assert (await ledger(seed.a.id))["sales"] == 0


async def test_failure_then_retry_success(client: AsyncClient, seed: Seed, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    out = (await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])).json()
    key = payment_key(out)
    assert (await notify(client, key, status="failed")).json()["outcome"] == "failed"
    order = (await client.get(f"/api/v1/student/orders/{out['order']['id']}", headers=student)).json()
    assert order["status"] == "failed"
    assert (await notify(client, key)).json()["outcome"] == "paid"      # out of order: success wins
    assert (await ledger(seed.a.id))["sales"] == 1


async def test_unknown_payment_is_ignored(client: AsyncClient) -> None:
    assert (await notify(client, "no-such-payment")).json()["outcome"] == "unknown payment"


async def test_paying_for_an_approved_past_month(client: AsyncClient, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    await client.post(f"/api/v1/student/classes/{k['class']['slug']}/enroll", headers=student)
    oct_ = k["months"]["closed"]["id"]
    req = (await client.post(f"/api/v1/student/months/{oct_}/late-request", headers=student, json={})).json()
    await client.post(f"/api/v1/org/late-requests/{req['id']}/decision", headers=teacher, json={"decision": "approve"})
    out = (await checkout(client, student, k["class"]["id"], oct_)).json()
    await notify(client, payment_key(out))
    view = (await client.get(f"/api/v1/student/classes/{k['class']['slug']}", headers=student)).json()
    assert {m["month_start"]: m["access"] for m in view["months"]}["2026-10-01"] == "granted"
    fulfilled = (await client.get("/api/v1/org/late-requests?status=fulfilled", headers=teacher)).json()
    assert [r["id"] for r in fulfilled] == [req["id"]]


async def test_one_time_class(client: AsyncClient, seed: Seed, teacher: Headers, student: Headers) -> None:
    c = (await client.post("/api/v1/org/classes", headers=teacher, json={
        "title": "Paper class", "pricing_model": "one_time", "one_time_price_cents": 350000})).json()
    lesson = (await client.post(f"/api/v1/org/classes/{c['id']}/lessons", headers=teacher,
                                json={"title": "Paper 1", "lesson_type": "document", "is_published": True})).json()
    await client.patch(f"/api/v1/org/classes/{c['id']}", headers=teacher, json={"status": "published"})
    out = (await checkout(client, student, c["id"])).json()
    assert out["order"]["total_cents"] == 350000
    await notify(client, payment_key(out), amount=350000)
    assert (await client.get(f"/api/v1/student/lessons/{lesson['id']}", headers=student)).json()["unlocked"] is True


# --- orders visibility, fee true-up, dev page -------------------------------------------------------

async def test_orders_are_private(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember,
                                  teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    out = (await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])).json()
    other = await auth_headers(client, sms, seed.a, await members(seed.a, "student"))
    assert (await client.get(f"/api/v1/student/orders/{out['order']['id']}", headers=other)).status_code == 404
    assert (await client.get("/api/v1/student/orders", headers=student)).json() == []      # pending isn't history
    await notify(client, payment_key(out))
    assert len((await client.get("/api/v1/student/orders", headers=student)).json()) == 1
    other_teacher = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    assert (await client.get("/api/v1/org/orders", headers=other_teacher)).json()["items"] == []


async def test_fee_true_up(client: AsyncClient, seed: Seed, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    out = (await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])).json()
    await notify(client, payment_key(out))
    async with tenant_transaction(seed.a.id) as s:
        payment_id = (await s.execute(text("SELECT id FROM payments WHERE status = 'succeeded'"))).scalar_one()
        await settle_fee(s, payment_id, 6500)
    assert (await ledger(seed.a.id))["balance"] == 153500
    with pytest.raises(IntegrityError):                       # booked at most once per payment
        async with tenant_transaction(seed.a.id) as s:
            await settle_fee(s, payment_id, 7000)


async def test_dev_gateway_page(client: AsyncClient, seed: Seed, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    out = (await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])).json()
    key = payment_key(out)
    page = await client.get(f"/api/v1/dev/fake-gateway/{key}",
                            params={"return_url": "http://x.localhost/r", "cancel_url": "http://x.localhost/c"})
    assert page.status_code == 200 and "LKR 2000.00" in page.text
    evil = await client.post(f"/api/v1/dev/fake-gateway/{key}", data={
        "outcome": "succeeded", "return_url": "https://evil.example/", "cancel_url": "https://evil.example/"})
    assert evil.status_code == 400
    done = await client.post(f"/api/v1/dev/fake-gateway/{key}", data={
        "outcome": "succeeded", "return_url": "http://x.localhost/r", "cancel_url": "http://x.localhost/c"})
    assert done.status_code == 303 and done.headers["location"] == "http://x.localhost/r"
    order = (await client.get(f"/api/v1/student/orders/{out['order']['id']}", headers=student)).json()
    assert order["status"] == "paid"


# --- isolation (CLAUDE.md section 5, rule 8) ----------------------------------------------------------

async def test_money_tables_isolated(client: AsyncClient, seed: Seed, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    out = (await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])).json()
    await notify(client, payment_key(out))
    tables = ("orders", "order_items", "payments", "ledger_transactions", "ledger_entries")
    async with tenant_transaction(seed.b.id) as s:
        for table in tables:
            seen = (await s.execute(text(f"SELECT count(*) FROM {table} WHERE tenant_id = :a"),
                                    {"a": seed.a.id})).scalar_one()
            assert seen == 0, table
        assert (await s.execute(text("SELECT count(*) FROM v_tenant_balance"))).scalar_one() == 0
