"""Step 8: cash flow and per-teacher earnings, read from the ledger."""

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from app.modules.checkout.service import settle_fee
from app.modules.ledger import posting
from tests.conftest import AddMember, FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_checkout import checkout, notify, payment_key
from tests.test_learning import monthly_class

Headers = dict[str, str]
THIS_MONTH = datetime.now(ZoneInfo("Asia/Colombo")).strftime("%Y-%m")


@pytest.fixture
async def owner(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember) -> Headers:
    return await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))


@pytest.fixture
async def teacher(client: AsyncClient, sms: FakeSms, seed: Seed) -> Headers:
    return await auth_headers(client, sms, seed.a, seed.a.teacher_phone)


async def sell(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember, teacher_h: Headers,
               **class_overrides: Any) -> str:
    """A new student buys the open month of a new class by `teacher_h`. Returns the payment key."""
    k = await monthly_class(client, teacher_h, **class_overrides)
    student = await auth_headers(client, sms, seed.a, await members(seed.a, "student"))
    out = (await checkout(client, student, k["class"]["id"], k["months"]["open"]["id"])).json()
    amount = out["order"]["total_cents"]
    assert (await notify(client, payment_key(out), amount=amount)).json()["outcome"] == "paid"
    return payment_key(out)


def this_month(cash: dict[str, Any]) -> dict[str, Any]:
    return next(m for m in cash["months"] if m["month"].startswith(THIS_MONTH))


async def test_cashflow_after_sales(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember,
                                    owner: Headers, teacher: Headers) -> None:
    await sell(client, sms, seed, members, teacher)
    cash = (await client.get("/api/v1/org/cashflow", headers=owner)).json()
    assert len(cash["months"]) == 12 and cash["months"][-1]["month"].startswith(THIS_MONTH)
    assert this_month(cash) == {
        "month": f"{THIS_MONTH}-01", "gross_sales_cents": 200000, "refunds_cents": 0, "gateway_fees_cents": 6000,
        "commission_cents": 40000, "net_cents": 154000, "paid_out_cents": 0,
    }
    assert cash["balance_due_cents"] == 154000 and cash["totals"]["net_cents"] == 154000
    assert (cash["currency"], cash["commission_bps"], cash["gateway_fee_bearer"]) == ("LKR", 2000, "tenant")
    # Months without activity are present with zeros.
    assert all(m["gross_sales_cents"] == 0 for m in cash["months"][:-1])


async def test_cashflow_true_up_refund_and_payout(client: AsyncClient, sms: FakeSms, seed: Seed,
                                                  members: AddMember, owner: Headers, teacher: Headers) -> None:
    key = await sell(client, sms, seed, members, teacher)
    async with tenant_transaction(seed.a.id) as s:
        p = (await s.execute(text("""
            SELECT p.id, i.id AS item_id, i.teacher_member_id FROM payments p
            JOIN order_items i ON i.order_id = p.order_id WHERE p.idempotency_key = :k
        """), {"k": key})).one()
        await settle_fee(s, p.id, 6500)                                       # fees 6500, net 153500
        await posting.post(s, kind="refund", entries=posting.refund_entries(  # half refunded
            refund=100000, gross=200000, commission_bps=2000, order_item_id=p.item_id,
            teacher_member_id=p.teacher_member_id))
        await posting.post(s, kind="payout", entries=posting.payout_entries(50000))
    cash = (await client.get("/api/v1/org/cashflow", headers=owner)).json()
    m = this_month(cash)
    assert m["gross_sales_cents"] == 200000                                   # as sold
    assert m["refunds_cents"] == 100000                                       # its own line
    assert m["gateway_fees_cents"] == 6500
    assert m["commission_cents"] == 20000                                     # after refunds
    assert m["net_cents"] == 153500 - 80000                                   # after refunds and true-up
    assert m["paid_out_cents"] == 50000
    assert cash["balance_due_cents"] == 153500 - 80000 - 50000


async def test_platform_borne_fees_dont_reduce_net(client: AsyncClient, sms: FakeSms, seed: Seed,
                                                   members: AddMember, owner: Headers, teacher: Headers) -> None:
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE tenants SET gateway_fee_bearer = 'platform' WHERE id = :t"), {"t": seed.a.id})
    await sell(client, sms, seed, members, teacher)
    cash = (await client.get("/api/v1/org/cashflow", headers=owner)).json()
    assert this_month(cash)["net_cents"] == 160000 and cash["gateway_fee_bearer"] == "platform"


async def test_cashflow_is_for_owners_and_admins(client: AsyncClient, teacher: Headers) -> None:
    resp = await client.get("/api/v1/org/cashflow", headers=teacher)
    assert resp.status_code == 403 and error_code(resp) == "ACCESS_DENIED"


@pytest.mark.parametrize(("query", "status"), [
    ("from=2026-10&to=2026-01", 400), ("from=2020-01&to=2026-10", 400), ("from=2026-13", 400),
    ("from=bad", 422), ("from=2026-01&to=2026-03", 200),
])
async def test_cashflow_ranges(client: AsyncClient, owner: Headers, query: str, status: int) -> None:
    resp = await client.get(f"/api/v1/org/cashflow?{query}", headers=owner)
    assert resp.status_code == status, resp.text
    if status == 200:
        assert [m["month"] for m in resp.json()["months"]] == ["2026-01-01", "2026-02-01", "2026-03-01"]


async def test_teacher_earnings(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember,
                                owner: Headers, teacher: Headers) -> None:
    other = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    await sell(client, sms, seed, members, teacher)
    await sell(client, sms, seed, members, teacher)
    await sell(client, sms, seed, members, other, monthly_fee_cents=150000)

    all_rows = (await client.get(f"/api/v1/org/earnings?month={THIS_MONTH}", headers=owner)).json()
    rows = {r["teacher_name"]: r for r in all_rows["teachers"]}
    assert rows["Teacher a"]["sales_count"] == 2
    assert rows["Teacher a"]["gross_sales_cents"] == 400000
    assert rows["Teacher a"]["commission_cents"] == 80000
    assert rows["Teacher a"]["net_cents"] == 2 * 154000
    other_name = next(n for n in rows if n != "Teacher a")
    assert rows[other_name]["net_cents"] == 150000 - 30000 - 4500
    assert all_rows["total_net_cents"] == 2 * 154000 + 115500

    mine = (await client.get("/api/v1/org/earnings", headers=teacher)).json()   # defaults to this month
    assert [r["teacher_name"] for r in mine["teachers"]] == ["Teacher a"]
    empty = (await client.get("/api/v1/org/earnings?month=2020-01", headers=owner)).json()
    assert empty["teachers"] == [] and empty["total_net_cents"] == 0


async def test_money_isolated_between_tenants(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember,
                                              teacher: Headers) -> None:
    await sell(client, sms, seed, members, teacher)
    owner_b = await auth_headers(client, sms, seed.b, await members(seed.b, "owner"))
    cash = (await client.get("/api/v1/org/cashflow", headers=owner_b)).json()
    assert cash["balance_due_cents"] == 0 and cash["totals"]["gross_sales_cents"] == 0
    earn = (await client.get("/api/v1/org/earnings", headers=owner_b)).json()
    assert earn["teachers"] == []
