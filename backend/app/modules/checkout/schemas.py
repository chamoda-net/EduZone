from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.modules.learning.schemas import OrgRef


class CheckoutCreate(BaseModel):
    """One item per order in v1: a month of a monthly class, or a one-time class."""

    model_config = ConfigDict(extra="forbid")

    class_id: UUID
    class_month_id: UUID | None = None


class OrderItemOut(BaseModel):
    id: UUID
    class_id: UUID
    class_slug: str | None             # None in cross-tenant lists (/learn/payments)
    class_month_id: UUID | None
    description: str
    amount_cents: int


class OrderOut(BaseModel):
    id: UUID
    order_no: str
    status: str                        # pending | paid | failed | cancelled | refunded | partially_refunded
    currency: str
    total_cents: int
    created_at: datetime
    paid_at: datetime | None
    method: str | None                 # from the successful payment
    card_last4: str | None
    item: OrderItemOut
    org: OrgRef | None = None          # set by /learn routes


class Redirect(BaseModel):
    method: Literal["GET", "POST"]
    url: str
    fields: dict[str, str]


class CheckoutOut(BaseModel):
    order: OrderOut
    redirect: Redirect


class OrgOrderRow(OrderOut):
    student_name: str
    student_phone: str | None


class OrgOrderPage(BaseModel):
    items: list[OrgOrderRow]
    next_cursor: str | None
