"""Ledger posting rules (CLAUDE.md section 7). The ledger is the source of truth for cash flow.

Pure functions build the entries (easy to test, always balanced); `post()` writes one
transaction. The database also enforces: append-only, every transaction sums to zero,
and each payment / refund / payout / fee settlement is booked once.

Sign convention: positive = debit, negative = credit. All amounts are integer cents.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

Account = Literal["gateway_clearing", "gateway_fees", "platform_commission", "tenant_payable", "bank"]
FeeBearer = Literal["tenant", "platform"]


@dataclass(frozen=True, slots=True)
class Entry:
    account: Account
    amount_cents: int
    order_item_id: UUID | None = None
    teacher_member_id: UUID | None = None


def commission_cents(amount_cents: int, commission_bps: int) -> int:
    """Round half up: (amount * bps + 5000) // 10000."""
    return (amount_cents * commission_bps + 5000) // 10000


def estimate_fee_cents(amount_cents: int, fee_bps: int) -> int:
    return (amount_cents * fee_bps + 5000) // 10000


def allocate(total_cents: int, weights: list[int]) -> list[int]:
    """Split `total_cents` in proportion to `weights` by largest remainder: every share is a whole cent and
    the shares always add up to the total exactly. Ties go to the earlier weight (deterministic)."""
    if total_cents < 0 or not weights or any(w < 0 for w in weights) or sum(weights) == 0:
        raise ValueError("allocate needs a non-negative total and positive weights")
    whole = sum(weights)
    shares = [total_cents * w // whole for w in weights]
    order = sorted(range(len(weights)), key=lambda i: (-(total_cents * weights[i] % whole), i))
    for i in order[: total_cents - sum(shares)]:
        shares[i] += 1
    return shares


def sale_entries(*, gross: int, fee: int, commission_bps: int, fee_bearer: FeeBearer,
                 order_item_id: UUID, teacher_member_id: UUID) -> list[Entry]:
    """G = gross, F = gateway fee, C = commission on G.
    Tenant bears the fee: tenant net = G - C - F. Platform bears it: tenant net = G - C."""
    c = commission_cents(gross, commission_bps)
    item, teacher = order_item_id, teacher_member_id
    entries = [
        Entry("gateway_clearing", gross - fee, item),
        Entry("gateway_fees", fee, item),
        Entry("platform_commission", -c, item),
        Entry("tenant_payable", -(gross - c), item, teacher),
    ]
    if fee_bearer == "tenant" and fee:
        entries += [Entry("tenant_payable", fee, item, teacher), Entry("gateway_fees", -fee, item)]
    return entries


def fee_settlement_entries(*, estimated: int, actual: int, fee_bearer: FeeBearer,
                           order_item_id: UUID, teacher_member_id: UUID) -> list[Entry]:
    """True-up when the settlement report gives the actual fee. D may be negative."""
    d = actual - estimated
    if d == 0:
        return []
    entries = [Entry("gateway_fees", d, order_item_id), Entry("gateway_clearing", -d, order_item_id)]
    if fee_bearer == "tenant":
        entries += [Entry("tenant_payable", d, order_item_id, teacher_member_id),
                    Entry("gateway_fees", -d, order_item_id)]
    return entries


def refund_entries(*, refund: int, gross: int, commission_bps: int, order_item_id: UUID,
                   teacher_member_id: UUID) -> list[Entry]:
    """Reverse proportionally: the commission share and the tenant's share of the refunded
    amount come back; the money leaves the gateway. The gateway usually keeps its fee, so
    whoever bore it at sale time keeps bearing it (nothing to post for fees here)."""
    # The refunded fraction of the commission actually booked, rounded half up.
    c_share = (commission_cents(gross, commission_bps) * refund + gross // 2) // gross
    return [
        Entry("tenant_payable", refund - c_share, order_item_id, teacher_member_id),
        Entry("platform_commission", c_share, order_item_id),
        Entry("gateway_clearing", -refund, order_item_id),
    ]


def payout_entries(amount: int) -> list[Entry]:
    return [Entry("tenant_payable", amount), Entry("bank", -amount)]


async def post(session: AsyncSession, *, kind: str, entries: list[Entry], payment_id: UUID | None = None,
               refund_id: UUID | None = None, payout_id: UUID | None = None, memo: str | None = None,
               created_by: UUID | None = None) -> UUID | None:
    """Write one balanced transaction in the current tenant. Returns None for no entries."""
    if not entries:
        return None
    if sum(e.amount_cents for e in entries) != 0:
        raise ValueError("unbalanced ledger transaction")  # the DB would refuse it at commit anyway
    tx_id = (await session.execute(text("""
        INSERT INTO ledger_transactions (tenant_id, kind, payment_id, refund_id, payout_id, memo, created_by)
        VALUES (current_tenant_id(), :kind, :payment, :refund, :payout, :memo, :by)
        RETURNING id
    """), {"kind": kind, "payment": payment_id, "refund": refund_id, "payout": payout_id, "memo": memo,
           "by": created_by})).scalar_one()
    await session.execute(text("""
        INSERT INTO ledger_entries (tenant_id, ledger_tx_id, account, amount_cents, order_item_id, teacher_member_id)
        VALUES (current_tenant_id(), :tx, :account, :amount, :item, :teacher)
    """), [{"tx": tx_id, "account": e.account, "amount": e.amount_cents, "item": e.order_item_id,
            "teacher": e.teacher_member_id} for e in entries if e.amount_cents != 0])
    return tx_id
