"""Courses, step C7: commission per product type with scheduled changes and notice (docs/COURSES.md C.10), and the
instructor analytics of a course (section 10)."""

from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from app.modules.platform import commission
from tests.conftest import AddMember, FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_courses import O, P, teacher  # noqa: F401  (fixtures)
from tests.test_learn import main_login
from tests.test_learn_courses import buy
from tests.test_market_courses import live_course
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
Phones = Callable[[], str]
C = f"{P}/commission"


def days(n: float) -> str:
    return (datetime.now(UTC) + timedelta(days=n)).isoformat()


class Outbox:
    def __init__(self) -> None:
        self.sent: list[tuple[str, str, str]] = []

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))


@pytest.fixture(autouse=True)
async def clean_rates(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[Outbox]:
    """Commission is platform-wide state: every test starts and ends at 20% with no changes."""
    outbox = Outbox()
    monkeypatch.setattr(commission, "get_email_sender", lambda: outbox)

    async def reset() -> None:
        async with AdminSession() as s, s.begin():
            await s.execute(text("DELETE FROM commission_changes"))
            await s.execute(text("UPDATE platform_commission_rates SET commission_bps = 2000"))
    await reset()
    yield outbox
    await reset()


async def make_due(change_id: str) -> None:
    """As if the effective date had arrived."""
    async with AdminSession() as s, s.begin():
        await s.execute(text("""
            UPDATE commission_changes SET announced_at = now() - interval '40 days',
                                          effective_at = now() - interval '1 minute'
            WHERE id = :id
        """), {"id": change_id})


async def item_rates(tenant_id: UUID, course_id: str) -> list[int]:
    async with tenant_transaction(tenant_id) as s:
        return list((await s.execute(text("""
            SELECT i.commission_bps FROM order_items i JOIN orders o ON o.id = i.order_id
            WHERE i.class_id = :c AND o.status = 'paid' ORDER BY o.created_at
        """), {"c": course_id})).scalars())


@pytest.fixture
async def course(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers) -> dict[str, Any]:  # noqa: F811
    return await live_course(client, seed, teacher, ph, f"Switching {uuid4().hex[:6]}")


# --- scheduling rules -------------------------------------------------------------------------------

async def test_scheduling_rules(client: AsyncClient, seed: Seed, ph: Headers, clean_rates: Outbox) -> None:  # noqa: F811
    overview = (await client.get(C, headers=ph)).json()
    assert overview["notice_days"] == 30
    assert {r["kind"]: r["commission_bps"] for r in overview["rates"]} == {"tuition": 2000, "course": 2000}

    async def schedule(**body: Any) -> Any:
        return await client.post(f"{C}/changes", headers=ph, json={
            "scope": "platform", "kind": "course", "reason": "Launch pricing", **body})

    short = await schedule(new_bps=2500, effective_at=days(10))
    assert short.status_code == 422 and error_code(short) == "COMMISSION_NOTICE_TOO_SHORT"
    assert error_code(await schedule(new_bps=2000, effective_at=days(40))) == "COMMISSION_UNCHANGED"
    assert error_code(await schedule(new_bps=1500, effective_at=days(-1))) == "COMMISSION_DATE_PAST"
    assert error_code(await schedule(scope="tenant", new_bps=1500, effective_at=days(5))) == "TENANT_REQUIRED"

    # A decrease may come sooner; an increase with full notice is fine.
    down = await schedule(new_bps=1500, effective_at=days(2))
    assert down.status_code == 201, down.text
    change = down.json()
    assert (change["old_bps"], change["new_bps"], change["status"]) == (2000, 1500, "scheduled")
    notified = {n["tenant_id"] for n in change["notified"]}
    assert str(seed.a.id) in notified and str(seed.b.id) in notified
    assert any("15%" in body and "20%" in body for _, _, body in clean_rates.sent)
    dup = await schedule(new_bps=1800, effective_at=days(3))
    assert dup.status_code == 409 and error_code(dup) == "COMMISSION_CHANGE_PENDING"
    up = await schedule(kind="tuition", new_bps=2200, effective_at=days(31))
    assert up.status_code == 201

    # Cancel until it takes effect; the same owners hear about it.
    sent = len(clean_rates.sent)
    cancelled = (await client.post(f"{C}/changes/{change['id']}/cancel", headers=ph)).json()
    assert cancelled["status"] == "cancelled" and len(clean_rates.sent) > sent
    again = await client.post(f"{C}/changes/{change['id']}/cancel", headers=ph)
    assert again.status_code == 409


# --- checkout uses the rate of the day; past sales keep theirs ---------------------------------------

async def test_due_change_applies_and_snapshots(client: AsyncClient, seed: Seed, course: dict[str, Any], ph: Headers,
                                                sms: FakeSms, phones: Phones, members: AddMember) -> None:  # noqa: F811
    cid = course["id"]
    await buy(client, await main_login(client, sms, phones()), cid)
    change = (await client.post(f"{C}/changes", headers=ph, json={
        "scope": "platform", "kind": "course", "new_bps": 1500, "effective_at": days(5), "reason": "Courses promo"})).json()
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    banner = (await client.get(f"{O}/commission", headers=owner)).json()
    assert [(b["kind"], b["old_bps"], b["new_bps"]) for b in banner] == [("course", 2000, 1500)]

    # Its day comes: checkout uses it at once, before anything marks it applied.
    await make_due(change["id"])
    await buy(client, await main_login(client, sms, phones()), cid)
    assert await item_rates(seed.a.id, cid) == [2000, 1500]
    money = (await client.get(f"{O}/cashflow", headers=owner)).json()
    assert (money["course_commission_bps"], money["tuition_commission_bps"]) == (1500, 2000)
    assert money["upcoming_changes"] == []

    # The admin page records it as applied; nothing changes for past sales.
    overview = (await client.get(C, headers=ph)).json()
    assert {r["kind"]: r["commission_bps"] for r in overview["rates"]}["course"] == 1500
    assert next(c for c in overview["changes"] if c["id"] == change["id"])["status"] == "applied"
    assert (await client.post(f"{C}/changes/{change['id']}/cancel", headers=ph)).status_code == 409
    assert await item_rates(seed.a.id, cid) == [2000, 1500]


async def test_tenant_override(client: AsyncClient, seed: Seed, ph: Headers, sms: FakeSms,  # noqa: F811
                               members: AddMember) -> None:
    own = (await client.post(f"{C}/changes", headers=ph, json={
        "scope": "tenant", "tenant_id": str(seed.a.id), "kind": "tuition", "new_bps": 1000, "effective_at": days(1),
        "reason": "Large institute"})).json()
    assert [n["tenant_id"] for n in own["notified"]] == [str(seed.a.id)]
    await make_due(own["id"])
    row = (await client.get(f"{P}/tenants/{seed.a.id}", headers=ph)).json()
    assert (row["tuition_commission_bps"], row["course_commission_bps"]) == (1000, 2000)

    # Once applied it is the organization's own rate: a platform-wide tuition change no longer touches it.
    await client.get(C, headers=ph)
    row = (await client.get(f"{P}/tenants/{seed.a.id}", headers=ph)).json()
    assert row["tuition_override_bps"] == 1000
    wide = (await client.post(f"{C}/changes", headers=ph, json={
        "scope": "platform", "kind": "tuition", "new_bps": 1800, "effective_at": days(2), "reason": "All"})).json()
    assert str(seed.a.id) not in {n["tenant_id"] for n in wide["notified"]}
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    assert (await client.get(f"{O}/commission", headers=owner)).json() == []
    # Commission isn't edited directly any more.
    patch = await client.patch(f"{P}/tenants/{seed.a.id}", headers=ph, json={"commission_bps": 500})
    assert patch.status_code == 422


# --- instructor analytics -------------------------------------------------------------------------

async def test_course_insights(client: AsyncClient, seed: Seed, teacher: Headers, course: dict[str, Any],  # noqa: F811
                               sms: FakeSms, phones: Phones, members: AddMember) -> None:
    cid = course["id"]
    code = "INS-" + uuid4().hex[:6].upper()
    await client.post(f"{O}/coupons", headers=teacher, json={
        "code": code, "course_id": cid, "discount_type": "percent", "percent_bps": 5000, "ends_at": days(30)})
    paid = await main_login(client, sms, phones())
    await buy(client, paid, cid)
    with_code = await main_login(client, sms, phones())
    await client.post("/api/v1/me/cart/items", headers=with_code, json={"class_id": cid, "coupon_code": code})
    from tests.test_cart import pay
    _, form = await pay(client, with_code, amount=150000)
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "paid"
    await client.post(f"/api/v1/learn/courses/{cid}/refund", headers=with_code, json={"reason": "Changed my mind"})
    await client.put(f"/api/v1/me/wishlist/{cid}", headers=await main_login(client, sms, phones()))

    r = await client.get(f"{O}/courses/{cid}/insights", headers=teacher)
    assert r.status_code == 200, r.text
    d = r.json()
    assert len(d["months"]) == 12 and d["months"][-1] == {**d["months"][-1], "enrol_paid": 1, "enrol_coupon": 1}
    t = d["totals"]
    assert (t["enrol_paid"], t["enrol_coupon"], t["enrol_free"]) == (1, 1, 0)
    assert (t["gross_cents"], t["refunds_cents"], t["refund_count"]) == (450000, 150000, 1)
    assert 0 < t["net_cents"] < t["gross_cents"] - t["refunds_cents"]          # after commission and fees
    assert d["students"] == 1 and d["completion_rate"] == 0 and d["wishlist_count"] == 1
    assert d["top_coupons"] == [{"code": code, "uses": 1, "discount_cents": 150000, "revenue_cents": 150000}]
    assert (await client.get(f"{O}/courses/{cid}/insights", params={"months": 3}, headers=teacher)).json()["months"][0]
    other = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    assert (await client.get(f"{O}/courses/{cid}/insights", headers=other)).status_code == 404
