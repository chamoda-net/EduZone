"""Cash flow and per-teacher earnings (build step 8). Read-only, and only from the ledger
(CLAUDE.md section 7: never from orders or payments). Months are Asia/Colombo calendar months.

Who sees what: the organization's cash flow is for owners and admins. Earnings: owners and
admins see every teacher; a teacher sees only their own row.
"""

from datetime import date
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.auth.dependencies import Actor
from app.modules.ledger.schemas import Cashflow, CashflowMonth, CashflowTotals, Earnings, TeacherEarning

MAX_MONTHS = 36


def parse_month(value: str | None, field: str) -> date | None:
    """'2026-10' -> date(2026, 10, 1)."""
    if value is None:
        return None
    try:
        y, m = value.split("-")
        return date(int(y), int(m), 1)
    except ValueError:
        raise ApiError("BAD_REQUEST", f"{field} must look like 2026-10.", status_code=400) from None


def _add_months(d: date, n: int) -> date:
    total = d.year * 12 + d.month - 1 + n
    return date(total // 12, total % 12 + 1, 1)


def _months_between(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + end.month - start.month + 1


def _require_money_access(actor: Actor) -> None:
    if not actor.manages_all:
        raise ApiError("ACCESS_DENIED", "Only owners and admins can see the organization's money.", 403)


async def _current_month(session: AsyncSession) -> date:
    return (await session.execute(text(
        "SELECT date_trunc('month', now() AT TIME ZONE 'Asia/Colombo')::date"))).scalar_one()


async def cashflow(session: AsyncSession, actor: Actor, *, start: date | None, end: date | None) -> Cashflow:
    _require_money_access(actor)
    end = end or await _current_month(session)
    start = start or _add_months(end, -11)
    if start > end:
        raise ApiError("BAD_REQUEST", "'from' must not be after 'to'.", status_code=400)
    if _months_between(start, end) > MAX_MONTHS:
        raise ApiError("BAD_REQUEST", f"Choose at most {MAX_MONTHS} months.", status_code=400)

    tenant = (await session.execute(text("""
        SELECT t.currency, t.commission_bps, t.gateway_fee_bearer,
               COALESCE((SELECT balance_due_cents FROM v_tenant_balance), 0) AS balance_due_cents
        FROM tenants t WHERE t.id = current_tenant_id()
    """))).one()
    rows = {r.month: r for r in (await session.execute(text("""
        SELECT month, gross_sales_cents, refunds_cents, gateway_fees_cents, eduzone_commission_cents,
               net_earned_cents, paid_out_cents
        FROM v_tenant_cashflow_monthly
        WHERE month BETWEEN :start AND :end
    """), {"start": start, "end": end})).all()}

    months = []
    for i in range(_months_between(start, end)):
        m = _add_months(start, i)
        r = rows.get(m)
        months.append(CashflowMonth(
            month=m,
            gross_sales_cents=int(r.gross_sales_cents) if r else 0,
            refunds_cents=int(r.refunds_cents) if r else 0,
            gateway_fees_cents=int(r.gateway_fees_cents) if r else 0,
            commission_cents=int(r.eduzone_commission_cents) if r else 0,
            net_cents=int(r.net_earned_cents) if r else 0,
            paid_out_cents=int(r.paid_out_cents) if r else 0,
        ))
    totals = CashflowTotals(**{
        field: sum(getattr(m, field) for m in months) for field in CashflowTotals.model_fields
    })
    return Cashflow(currency=tenant.currency, commission_bps=tenant.commission_bps,
                    gateway_fee_bearer=tenant.gateway_fee_bearer, balance_due_cents=int(tenant.balance_due_cents),
                    months=months, totals=totals)


async def earnings(session: AsyncSession, actor: Actor, *, month: date | None) -> Earnings:
    month = month or await _current_month(session)
    rows: list[Any] = (await session.execute(text("""
        WITH e AS (
            SELECT i.teacher_member_id, lt.kind, le.account, le.amount_cents, le.order_item_id
            FROM ledger_entries le
            JOIN ledger_transactions lt ON lt.id = le.ledger_tx_id
            JOIN order_items i ON i.id = le.order_item_id
            WHERE date_trunc('month', lt.occurred_at AT TIME ZONE 'Asia/Colombo')::date = :month
              AND (CAST(:teacher AS uuid) IS NULL OR i.teacher_member_id = :teacher)
        )
        SELECT e.teacher_member_id, COALESCE(tm.display_name, u.full_name) AS teacher_name,
               count(DISTINCT e.order_item_id) FILTER (WHERE e.kind = 'sale') AS sales_count,
               COALESCE(sum(e.amount_cents) FILTER (WHERE e.kind = 'sale' AND (e.account = 'gateway_clearing'
                   OR (e.account = 'gateway_fees' AND e.amount_cents > 0))), 0) AS gross_sales_cents,
               COALESCE(-sum(e.amount_cents) FILTER (WHERE e.kind = 'refund' AND e.account = 'gateway_clearing'), 0)
                   AS refunds_cents,
               COALESCE(-sum(e.amount_cents) FILTER (WHERE e.account = 'platform_commission'), 0) AS commission_cents,
               COALESCE(-sum(e.amount_cents) FILTER (WHERE e.account = 'tenant_payable'), 0) AS net_cents
        FROM e
        JOIN tenant_members tm ON tm.id = e.teacher_member_id
        JOIN users u ON u.id = tm.user_id
        GROUP BY e.teacher_member_id, teacher_name
        ORDER BY net_cents DESC, teacher_name
    """), {"month": month, "teacher": None if actor.manages_all else actor.auth.member_id})).all()
    currency = (await session.execute(text("SELECT currency FROM tenants WHERE id = current_tenant_id()"))).scalar_one()
    teachers = [TeacherEarning(teacher_member_id=r.teacher_member_id, teacher_name=r.teacher_name,
                               sales_count=r.sales_count, gross_sales_cents=int(r.gross_sales_cents),
                               refunds_cents=int(r.refunds_cents), commission_cents=int(r.commission_cents),
                               net_cents=int(r.net_cents)) for r in rows]
    return Earnings(month=month, currency=currency, teachers=teachers,
                    total_net_cents=sum(t.net_cents for t in teachers))
