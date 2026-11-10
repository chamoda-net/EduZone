"""Courses, step C6 (docs/COURSES.md section 9): refunds. The rule (7 days, under 30%, no certificate, something
paid), automatic approval and the abuse limit, the queue, gateway outcomes (processed, manual, failed), what a
processed refund undoes (ledger, grant, certificate, review, order), and the 7-day payout hold."""

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.tenancy import tenant_transaction
from app.integrations.gateways.base import RefundResult
from app.integrations.gateways.fake import FakeGateway
from app.modules.courses import refunds
from tests.conftest import AddMember, FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_courses import O, P, teacher  # noqa: F401  (fixtures)
from tests.test_learn import main_login
from tests.test_learn_courses import buy, lectures
from tests.test_market_courses import live_course
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
Phones = Callable[[], str]
L = "/api/v1/learn"


@pytest.fixture
async def course(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers) -> dict[str, Any]:  # noqa: F811
    """A paid course (Rs. 3,000) with 5 lectures."""
    return await live_course(client, seed, teacher, ph, f"Routing {uuid4().hex[:6]}")


@pytest.fixture
async def student(client: AsyncClient, sms: FakeSms, phones: Phones) -> Headers:
    return await main_login(client, sms, phones())


async def view(client: AsyncClient, h: Headers, course_id: str) -> dict[str, Any]:
    return (await client.get(f"{L}/courses/{course_id}", headers=h)).json()


async def ask(client: AsyncClient, h: Headers, course_id: str) -> Any:
    return await client.post(f"{L}/courses/{course_id}/refund", headers=h, json={"reason": "Not what I expected"})


async def ledger(tenant_id: UUID, course_id: str, kind: str) -> dict[str, int]:
    async with tenant_transaction(tenant_id) as s:
        rows = (await s.execute(text("""
            SELECT le.account, sum(le.amount_cents) AS amount FROM ledger_entries le
            JOIN ledger_transactions lt ON lt.id = le.ledger_tx_id AND lt.kind = :k
            JOIN order_items i ON i.id = le.order_item_id WHERE i.class_id = :c GROUP BY le.account
        """), {"c": course_id, "k": kind})).all()
    return {r.account: int(r.amount) for r in rows}


async def item_state(tenant_id: UUID, course_id: str) -> Any:
    async with tenant_transaction(tenant_id) as s:
        return (await s.execute(text("""
            SELECT o.status AS order_status, p.status AS payment_status, i.refunded_at,
                   (SELECT count(*) FROM access_grants g WHERE g.order_item_id = i.id AND g.revoked_at IS NULL) AS live
            FROM order_items i JOIN orders o ON o.id = i.order_id JOIN payments p ON p.order_id = o.id
            WHERE i.class_id = :c ORDER BY o.created_at DESC LIMIT 1
        """), {"c": course_id})).one()


# --- the automatic path ---------------------------------------------------------------------------

async def test_auto_refund_undoes_the_sale(client: AsyncClient, seed: Seed, course: dict[str, Any],
                                           student: Headers) -> None:
    cid = course["id"]
    assert (await view(client, student, cid))["refund"] is None                   # not bought: nothing to say
    await buy(client, student, cid)
    await client.put(f"{L}/courses/{cid}/review", headers=student, json={"rating": 1, "comment": "Meh"})
    info = (await view(client, student, cid))["refund"]
    assert info["eligible"] and info["amount_cents"] == 300000 and info["deadline"] and info["refund"] is None

    r = await ask(client, student, cid)
    assert r.status_code == 201, r.text
    assert r.json()["status"] == "processed" and r.json()["auto_approved"]

    after = await view(client, student, cid)
    assert after["has_access"] is False
    assert after["refund"]["refund"]["status"] == "processed" and not after["refund"]["eligible"]
    state = await item_state(seed.a.id, cid)
    assert (state.order_status, state.payment_status, state.live) == ("refunded", "refunded", 0)
    assert state.refunded_at is not None
    # The ledger reverses the sale: the student's money leaves the gateway, commission and the teacher's share return.
    books = await ledger(seed.a.id, cid, "refund")
    assert books == {"gateway_clearing": -300000, "platform_commission": 60000, "tenant_payable": 240000}
    # The review is hidden and no longer counts.
    async with tenant_transaction(seed.a.id) as s:
        rv = (await s.execute(text("SELECT status, hidden_reason FROM course_reviews WHERE class_id = :c"),
                              {"c": cid})).one()
        rating = (await s.execute(text("SELECT rating_count FROM classes WHERE id = :c"), {"c": cid})).scalar_one()
    assert (rv.status, rv.hidden_reason, rating) == ("hidden", "Refunded", 0)
    # Nothing left to refund; the course can be bought again.
    again = await ask(client, student, cid)
    assert again.status_code == 409
    added = await client.post("/api/v1/me/cart/items", headers=student, json={"class_id": cid})
    assert added.status_code == 201


# --- the rule ------------------------------------------------------------------------------------

async def test_rule(client: AsyncClient, seed: Seed, teacher: Headers, course: dict[str, Any],  # noqa: F811
                    student: Headers, sms: FakeSms, phones: Phones) -> None:
    cid = course["id"]
    stranger = await ask(client, student, cid)
    assert stranger.status_code == 409 and error_code(stranger) == "REFUND_NOT_BOUGHT"
    await buy(client, student, cid)

    # 30% or more complete (2 of 5 lectures = 40%).
    for lec in lectures(await view(client, student, cid))[-2:]:
        await client.post(f"{L}/lectures/{lec['id']}/complete", headers=student)
    blocked = await ask(client, student, cid)
    assert blocked.status_code == 409 and error_code(blocked) == "REFUND_PROGRESS"
    assert (await view(client, student, cid))["refund"]["blocked_by"] == "REFUND_PROGRESS"
    for lec in lectures(await view(client, student, cid))[-2:]:
        await client.delete(f"{L}/lectures/{lec['id']}/complete", headers=student)

    # More than 7 days after paying.
    async with tenant_transaction(seed.a.id) as s:
        await s.execute(text("""
            UPDATE orders SET paid_at = now() - interval '8 days'
            WHERE id IN (SELECT order_id FROM order_items WHERE class_id = :c)
        """), {"c": cid})
    late = await ask(client, student, cid)
    assert late.status_code == 409 and error_code(late) == "REFUND_WINDOW_PASSED"

    # A purchase a coupon made free has nothing to refund.
    other = await main_login(client, sms, phones())
    code = "FREE-" + uuid4().hex[:6].upper()
    await client.post(f"{O}/coupons", headers=teacher, json={
        "code": code, "course_id": cid, "discount_type": "percent", "percent_bps": 10000, "ends_at": _days(30)})
    await client.post("/api/v1/me/cart/items", headers=other, json={"class_id": cid, "coupon_code": code})
    assert (await client.post("/api/v1/me/checkouts", headers=other)).json()["checkout"]["status"] == "paid"
    free = await ask(client, other, cid)
    assert free.status_code == 409 and error_code(free) == "REFUND_NOTHING_PAID"


def _days(n: int) -> str:
    return (datetime.now(UTC) + timedelta(days=n)).isoformat()


# --- the queue -------------------------------------------------------------------------------------

async def test_queue_and_gateway_outcomes(client: AsyncClient, seed: Seed, course: dict[str, Any], student: Headers,
                                          ph: Headers, monkeypatch: pytest.MonkeyPatch) -> None:  # noqa: F811
    cid = course["id"]
    await buy(client, student, cid)
    monkeypatch.setattr(refunds, "AUTO_LIMIT", 0)                 # as if the student had 3 recent refunds
    r = await ask(client, student, cid)
    assert r.status_code == 201 and r.json()["status"] == "requested" and not r.json()["auto_approved"]
    assert error_code(await ask(client, student, cid)) == "REFUND_OPEN"
    info = (await view(client, student, cid))["refund"]
    assert info["blocked_by"] == "REFUND_OPEN" and info["refund"]["status"] == "requested"
    assert (await view(client, student, cid))["has_access"]       # still learning while EduZone decides
    rid = r.json()["id"]

    queue = (await client.get(f"{P}/refunds", headers=ph)).json()
    assert rid in {x["id"] for x in queue["items"]}
    detail = (await client.get(f"{P}/refunds/{rid}", headers=ph)).json()
    assert detail["progress_percent"] == 0 and detail["recent_refunds"] == 1 and detail["gateway"] == "fake"
    assert detail["course_title"] == course["title"] and detail["gateway_payment_ref"]
    no_note = await client.post(f"{P}/refunds/{rid}/decision", headers=ph, json={"decision": "reject"})
    assert no_note.status_code == 422

    # The gateway can't refund through its API: it waits as approved; staff record the portal's reference.
    async def manual(self: FakeGateway, *a: Any) -> RefundResult:
        return RefundResult(status="manual", message="Use the portal.")
    monkeypatch.setattr(FakeGateway, "refund", manual)
    out = (await client.post(f"{P}/refunds/{rid}/decision", headers=ph,
                             json={"decision": "approve", "note": "Fair request"})).json()
    assert out["status"] == "approved" and out["failure_reason"].startswith("manual")
    assert (await view(client, student, cid))["has_access"]

    # A failed retry keeps it waiting; recording the portal's refund finishes it.
    async def failing(self: FakeGateway, *a: Any) -> RefundResult:
        return RefundResult(status="failed", message="Declined")
    monkeypatch.setattr(FakeGateway, "refund", failing)
    retried = (await client.post(f"{P}/refunds/{rid}/retry", headers=ph)).json()
    assert retried["status"] == "approved" and retried["failure_reason"].startswith("failed")
    done = (await client.post(f"{P}/refunds/{rid}/mark-processed", headers=ph,
                              json={"gateway_refund_ref": "PH-RF-1234"})).json()
    assert done["status"] == "processed" and done["gateway_refund_ref"] == "PH-RF-1234"
    assert (await view(client, student, cid))["has_access"] is False
    assert (await ledger(seed.a.id, cid, "refund"))["gateway_clearing"] == -300000
    # Exactly once: recording it again changes nothing.
    again = await client.post(f"{P}/refunds/{rid}/mark-processed", headers=ph, json={"gateway_refund_ref": "X-2"})
    assert again.status_code == 409
    assert (await ledger(seed.a.id, cid, "refund"))["gateway_clearing"] == -300000


async def test_rejected_and_certificate_revoked(client: AsyncClient, seed: Seed, course: dict[str, Any],
                                                student: Headers, ph: Headers,  # noqa: F811
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    cid = course["id"]
    await buy(client, student, cid)
    monkeypatch.setattr(refunds, "AUTO_LIMIT", 0)
    rid = (await ask(client, student, cid)).json()["id"]
    rejected = (await client.post(f"{P}/refunds/{rid}/decision", headers=ph,
                                  json={"decision": "reject", "note": "Most of the course was watched"})).json()
    assert rejected["status"] == "rejected"
    info = (await view(client, student, cid))["refund"]
    assert info["refund"]["decision_note"] == "Most of the course was watched" and info["eligible"]   # may ask again

    # A second request; the student finishes the course meanwhile and gets a certificate; approval revokes it.
    rid2 = (await ask(client, student, cid)).json()["id"]
    for lec in lectures(await view(client, student, cid)):
        await client.post(f"{L}/lectures/{lec['id']}/complete", headers=student)
    assert (await view(client, student, cid))["certificate_no"]
    await client.post(f"{P}/refunds/{rid2}/decision", headers=ph, json={"decision": "approve"})
    async with tenant_transaction(seed.a.id) as s:
        cert = (await s.execute(text("SELECT revoke_reason FROM certificates WHERE class_id = :c"),
                                {"c": cid})).scalar_one()
    assert cert == "refunded"
    assert (await view(client, student, cid))["certificate_no"] is None


# --- the payout hold --------------------------------------------------------------------------------

async def test_payout_hold(client: AsyncClient, seed: Seed, course: dict[str, Any], student: Headers,
                           ph: Headers, sms: FakeSms, members: AddMember) -> None:  # noqa: F811
    cid = course["id"]
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    before = (await client.get(f"{O}/cashflow", headers=owner)).json()
    await buy(client, student, cid)
    money = (await client.get(f"{O}/cashflow", headers=owner)).json()
    net = money["balance_due_cents"] - before["balance_due_cents"]
    assert net > 0 and money["pending_cents"] - before["pending_cents"] == net
    assert money["available_cents"] == money["balance_due_cents"] - money["pending_cents"]
    row = (await client.get(f"{P}/tenants/{seed.a.id}", headers=ph)).json()
    assert row["pending_cents"] == money["pending_cents"]

    payout = {"amount_cents": money["balance_due_cents"], "period_start": str(date.today()),
              "period_end": str(date.today()), "bank_reference": "TEST-HOLD"}
    held = await client.post(f"{P}/tenants/{seed.a.id}/payouts", headers=ph, json=payout)
    assert held.status_code == 409 and error_code(held) == "PAYOUT_EXCEEDS_AVAILABLE"

    # After the window the sale is available.
    async with tenant_transaction(seed.a.id) as s:
        await s.execute(text("""
            UPDATE orders SET paid_at = now() - interval '8 days'
            WHERE id IN (SELECT order_id FROM order_items WHERE class_id = :c)
        """), {"c": cid})
    money = (await client.get(f"{O}/cashflow", headers=owner)).json()
    assert money["pending_cents"] == before["pending_cents"]
    paid = await client.post(f"{P}/tenants/{seed.a.id}/payouts", headers=ph,
                             json={**payout, "amount_cents": money["available_cents"]})
    assert paid.status_code == 201, paid.text
