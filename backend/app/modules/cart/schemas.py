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
    coupon_code: str | None = Field(default=None, pattern=r"^[A-Za-z0-9-]{4,20}$")   # courses only


class CouponIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^[A-Za-z0-9-]{4,20}$")


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
    amount_cents: int | None           # what it costs now, after any coupon; None when it can't be priced
    list_price_cents: int | None       # before the coupon
    discount_cents: int = 0
    coupon_code: str | None = None     # the coupon giving the discount (a typed code or the course's sale)
    coupon_public: bool = False        # True for an automatic sale
    currency: str
    # Why it can't be paid now (an error code: ALREADY_HAS_ACCESS, LATE_APPROVAL_REQUIRED, MONTH_NOT_OPEN,
    # UNAVAILABLE, ...); None when it's ready. Items with a problem are left out of the total.
    problem: str | None


class Cart(BaseModel):
    items: list[CartItemOut]
    subtotal_cents: int                # before coupons (items that can be paid now)
    discount_cents: int
    total_cents: int
    codes: list[str]                   # codes the student applied that discount at least one item
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
