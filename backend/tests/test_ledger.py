"""Ledger posting rules (CLAUDE.md section 7): every transaction balances, rounding is half
up, and the worked example nets the tenant exactly Rs 1,540.00."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.tenancy import tenant_transaction
from app.modules.ledger import posting
from tests.conftest import Seed

ITEM, TEACHER = uuid.uuid4(), uuid.uuid4()


def total(entries: list[posting.Entry], account: str) -> int:
    return sum(e.amount_cents for e in entries if e.account == account)


@pytest.mark.parametrize(("bearer", "tenant_net"), [("tenant", 154000), ("platform", 160000)])
def test_worked_example(bearer: posting.FeeBearer, tenant_net: int) -> None:
    entries = posting.sale_entries(gross=200000, fee=6000, commission_bps=2000, fee_bearer=bearer,
                                   order_item_id=ITEM, teacher_member_id=TEACHER)
    assert sum(e.amount_cents for e in entries) == 0
    assert -total(entries, "tenant_payable") == tenant_net
    assert -total(entries, "platform_commission") == 40000
    assert total(entries, "gateway_clearing") == 194000
    assert all(e.teacher_member_id == TEACHER for e in entries if e.account == "tenant_payable")


@pytest.mark.parametrize(("amount", "bps", "expected"), [
    (1, 5000, 1),          # 0.5 rounds up
    (3, 5000, 2),          # 1.5 rounds up
    (199999, 2000, 40000),  # 39999.8
    (100001, 2000, 20000),  # 20000.2
    (0, 2000, 0),
])
def test_commission_rounds_half_up(amount: int, bps: int, expected: int) -> None:
    assert posting.commission_cents(amount, bps) == expected


@pytest.mark.parametrize("actual", [6500, 5200, 6000])
@pytest.mark.parametrize("bearer", ["tenant", "platform"])
def test_fee_settlement_balances(actual: int, bearer: posting.FeeBearer) -> None:
    entries = posting.fee_settlement_entries(estimated=6000, actual=actual, fee_bearer=bearer,
                                             order_item_id=ITEM, teacher_member_id=TEACHER)
    assert sum(e.amount_cents for e in entries) == 0
    expected_tenant_shift = (actual - 6000) if bearer == "tenant" else 0
    assert total(entries, "tenant_payable") == expected_tenant_shift


def test_full_refund_reverses_commission_and_tenant_share() -> None:
    sale = posting.sale_entries(gross=200000, fee=6000, commission_bps=2000, fee_bearer="tenant",
                                order_item_id=ITEM, teacher_member_id=TEACHER)
    refund = posting.refund_entries(refund=200000, gross=200000, commission_bps=2000, order_item_id=ITEM,
                                    teacher_member_id=TEACHER)
    assert sum(e.amount_cents for e in refund) == 0
    both = sale + refund
    assert total(both, "platform_commission") == 0
    assert -total(both, "tenant_payable") == -6000   # the gateway kept its fee; the tenant bore it


def test_partial_refund_is_proportional() -> None:
    refund = posting.refund_entries(refund=50000, gross=200000, commission_bps=2000, order_item_id=ITEM,
                                    teacher_member_id=TEACHER)
    assert total(refund, "platform_commission") == 10000
    assert total(refund, "tenant_payable") == 40000
    assert total(refund, "gateway_clearing") == -50000


def test_payout_balances() -> None:
    assert sum(e.amount_cents for e in posting.payout_entries(154000)) == 0


async def test_unbalanced_post_is_refused(seed: Seed) -> None:
    with pytest.raises(ValueError, match="unbalanced"):
        async with tenant_transaction(seed.a.id) as session:
            await posting.post(session, kind="adjustment",
                               entries=[posting.Entry("tenant_payable", -100), posting.Entry("bank", 99)])


async def test_ledger_is_append_only_for_the_app(seed: Seed) -> None:
    async with tenant_transaction(seed.a.id) as session:
        await posting.post(session, kind="adjustment", memo="test",
                           entries=[posting.Entry("tenant_payable", -100), posting.Entry("bank", 100)])
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_transaction(seed.a.id) as session:
            await session.execute(text("UPDATE ledger_entries SET amount_cents = 1"))
    with pytest.raises(DBAPIError, match="permission denied"):
        async with tenant_transaction(seed.a.id) as session:
            await session.execute(text("DELETE FROM ledger_transactions"))
