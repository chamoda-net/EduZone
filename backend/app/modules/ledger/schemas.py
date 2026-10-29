from datetime import date
from uuid import UUID

from pydantic import BaseModel


class CashflowMonth(BaseModel):
    """One calendar month (Asia/Colombo), all from the ledger. Gross is as sold; refunds are
    their own line; commission and net are AFTER refunds and fee true-ups."""

    month: date
    gross_sales_cents: int
    refunds_cents: int
    gateway_fees_cents: int
    commission_cents: int
    net_cents: int
    paid_out_cents: int


class CashflowTotals(BaseModel):
    gross_sales_cents: int
    refunds_cents: int
    gateway_fees_cents: int
    commission_cents: int
    net_cents: int
    paid_out_cents: int


class Cashflow(BaseModel):
    currency: str
    commission_bps: int                  # current rate (history uses each sale's own snapshot)
    gateway_fee_bearer: str              # tenant | platform
    balance_due_cents: int               # what EduZone owes the organization now (all time)
    months: list[CashflowMonth]          # oldest first, every month in the range
    totals: CashflowTotals               # for the range


class TeacherEarning(BaseModel):
    teacher_member_id: UUID
    teacher_name: str
    sales_count: int
    gross_sales_cents: int
    refunds_cents: int
    commission_cents: int
    net_cents: int                       # after commission, refunds and fees borne by the organization


class Earnings(BaseModel):
    month: date
    currency: str
    teachers: list[TeacherEarning]
    total_net_cents: int
