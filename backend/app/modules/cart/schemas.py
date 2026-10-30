from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.checkout.schemas import OrderOut, Redirect
from app.modules.learning.schemas import OrgRef

MAX_CART_ITEMS = 20


class CartItemIn(BaseModel):
    """A month of a monthly class, or a one-time class."""

    model_config = ConfigDict(extra="forbid")

    class_id: UUID
    class_month_id: UUID | None = None


class CartMerge(BaseModel):
    """The browser's cart (kept in a cookie before sign-in), added to the account's cart after sign-in."""

    items: list[CartItemIn] = Field(max_length=MAX_CART_ITEMS)


class CartItemOut(BaseModel):
    id: UUID | None                    # None in a guest preview (nothing stored yet)
    class_id: UUID
    class_month_id: UUID | None
    title: str
    path: str                          # the class's marketplace page
    subject_name: str
    teacher_name: str
    teacher_photo_url: str | None
    org: OrgRef
    cover_image_url: str | None
    month_start: date | None
    amount_cents: int | None           # None when it can't be priced (see problem)
    currency: str
    # Why it can't be paid now (an error code: ALREADY_HAS_ACCESS, LATE_APPROVAL_REQUIRED, MONTH_NOT_OPEN,
    # UNAVAILABLE, ...); None when it's ready. Items with a problem are left out of the total.
    problem: str | None


class Cart(BaseModel):
    items: list[CartItemOut]
    total_cents: int
    currency: str
    ready: bool                        # at least one item and no problems: checkout may start


class CheckoutDetail(BaseModel):
    id: UUID
    checkout_no: str
    status: str                        # pending | paid | failed | cancelled
    payment_status: str                # initiated | succeeded | failed | cancelled
    currency: str
    total_cents: int
    created_at: datetime
    paid_at: datetime | None
    method: str | None
    card_last4: str | None
    orders: list[OrderOut]


class CheckoutStarted(BaseModel):
    checkout: CheckoutDetail
    redirect: Redirect
