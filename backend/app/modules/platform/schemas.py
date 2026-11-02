from datetime import date, datetime
from typing import Annotated, Any, ClassVar, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.modules.catalog.schemas import _Patch

OrgType = Literal["individual", "institute", "corporate"]
TenantStatus = Literal["pending", "active", "suspended", "closed"]
FeeBearer = Literal["tenant", "platform"]

# Subdomains no organization can take.
RESERVED_SLUGS = frozenset({
    "admin", "api", "www", "app", "apply", "learn", "teach", "t", "login", "register", "support", "status", "mail",
    "static", "assets", "platform", "dev", "staging", "eduzone",
})


def _slug(v: str) -> str:
    if v in RESERVED_SLUGS:
        raise ValueError("this address is reserved")
    return v


Slug = Annotated[str, Field(pattern=r"^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$"), AfterValidator(_slug)]
Color = Annotated[str, Field(pattern=r"^#[0-9A-Fa-f]{6}$")]


class TenantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    slug: Slug
    org_type: OrgType = "individual"
    commission_bps: int = Field(default=2000, ge=0, le=10000)
    gateway_fee_bearer: FeeBearer = "tenant"
    primary_color: Color | None = None
    bunny_library_id: int | None = Field(default=None, gt=0)
    storage_limit_bytes: int | None = Field(default=None, ge=0)
    bandwidth_limit_bytes: int | None = Field(default=None, ge=0)
    # The owner signs in with this email. A new account has no password yet: the owner sets one
    # with "Forgot password", which also proves the address. They verify their phone on first sign-in.
    owner_email: EmailStr = Field(max_length=254)
    owner_name: str = Field(min_length=1, max_length=120)

    @field_validator("owner_email")
    @classmethod
    def _email(cls, v: str) -> str:
        return v.strip().lower()


class TenantUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = ("name", "status", "is_listed", "commission_bps", "gateway_fee_bearer")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    status: TenantStatus | None = None
    is_listed: bool | None = None
    commission_bps: int | None = Field(default=None, ge=0, le=10000)
    gateway_fee_bearer: FeeBearer | None = None
    primary_color: Color | None = None
    logo_url: str | None = Field(default=None, max_length=1000)
    bunny_library_id: int | None = Field(default=None, gt=0)
    storage_limit_bytes: int | None = Field(default=None, ge=0)
    bandwidth_limit_bytes: int | None = Field(default=None, ge=0)
    payout_bank_name: str | None = Field(default=None, max_length=100)
    payout_account_masked: str | None = Field(default=None, max_length=30)


class TenantRow(BaseModel):
    id: UUID
    name: str
    slug: str
    org_type: str
    status: str
    is_listed: bool
    currency: str
    commission_bps: int
    gateway_fee_bearer: str
    primary_color: str | None
    logo_url: str | None
    bunny_library_id: int | None
    payout_bank_name: str | None
    payout_account_masked: str | None
    created_at: datetime
    members: int
    students: int
    balance_due_cents: int
    sales_this_month_cents: int
    # Usage (CLAUDE.md section 9). Storage from our own records; bandwidth from the daily sync.
    storage_used_bytes: int
    storage_limit_bytes: int | None
    bandwidth_this_month_bytes: int
    bandwidth_limit_bytes: int | None
    usage_synced_on: date | None


class TenantCreated(BaseModel):
    tenant: TenantRow
    owner_user_id: UUID
    owner_member_id: UUID


class PlatformPayment(BaseModel):
    order_id: UUID
    order_no: str
    status: str
    tenant_id: UUID
    tenant_name: str
    student_name: str
    student_phone: str | None
    description: str
    total_cents: int
    currency: str
    gateway: str | None
    gateway_payment_ref: str | None
    created_at: datetime
    paid_at: datetime | None


class PlatformPaymentPage(BaseModel):
    items: list[PlatformPayment]
    next_cursor: str | None


class PayoutCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount_cents: int = Field(gt=0)
    period_start: date
    period_end: date
    bank_reference: str = Field(min_length=3, max_length=100)

    @model_validator(mode="after")
    def _period(self) -> "PayoutCreate":
        if self.period_end < self.period_start:
            raise ValueError("period_end must not be before period_start")
        return self


class PayoutRow(BaseModel):
    id: UUID
    tenant_id: UUID
    amount_cents: int
    period_start: date
    period_end: date
    status: str
    bank_reference: str | None
    created_by_name: str | None
    sent_at: datetime | None
    created_at: datetime


# --- subjects (phase 8) ----------------------------------------------------------------------

class SubjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=60)
    slug: Annotated[str, Field(pattern=r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])$")]
    sort_order: int = Field(default=0, ge=0, le=10000)


class SubjectUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = ("name", "sort_order", "is_active")

    # The slug is the public URL (/physics) and never changes once created.
    name: str | None = Field(default=None, min_length=2, max_length=60)
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None


class SubjectRow(BaseModel):
    id: UUID
    slug: str
    name: str
    sort_order: int
    is_active: bool
    classes: int            # published classes that use it
    created_at: datetime


# --- users and devices (phase 8) -------------------------------------------------------------

class UserRow(BaseModel):
    id: UUID
    full_name: str
    email: str | None
    phone: str | None
    email_verified: bool
    phone_verified: bool
    is_platform_admin: bool
    last_login_at: datetime | None
    created_at: datetime
    memberships: int
    active_sessions: int


class UserMembership(BaseModel):
    member_id: UUID
    tenant_id: UUID
    tenant_name: str
    tenant_slug: str
    role: str
    status: str
    joined_at: datetime


class UserSession(BaseModel):
    id: UUID
    device_id: str
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
    revoke_reason: str | None
    active: bool


class UserDevice(BaseModel):
    id: UUID
    device_id: str
    user_agent: str | None
    trusted_at: datetime
    last_seen_at: datetime


class UserDetail(UserRow):
    has_password: bool
    google_linked: bool
    exam: str | None
    exam_year: int | None
    school: str | None
    member_of: list[UserMembership]
    sessions: list[UserSession]       # active ones, then the 10 most recently ended
    devices: list[UserDevice]         # trusted: signing in on them needs no SMS code


class SignedOut(BaseModel):
    sessions_ended: int


# --- checkouts (phase 8) ---------------------------------------------------------------------

CheckoutStatus = Literal["pending", "paid", "failed", "cancelled"]


class PlatformCheckout(BaseModel):
    id: UUID
    checkout_no: str
    status: str
    user_id: UUID
    student_name: str
    student_email: str | None
    student_phone: str | None
    total_cents: int
    currency: str
    payment_status: str | None      # the latest gateway attempt
    orders: int
    orders_paid: int
    # Paid at the gateway but not every order fulfilled: needs a retry.
    stuck: bool
    created_at: datetime
    paid_at: datetime | None


class PlatformCheckoutPage(BaseModel):
    items: list[PlatformCheckout]
    next_cursor: str | None


class CheckoutOrder(BaseModel):
    order_id: UUID
    order_no: str
    status: str
    tenant_id: UUID
    tenant_name: str
    description: str
    total_cents: int
    gateway_fee_cents: int | None
    paid_at: datetime | None


class CheckoutAttempt(BaseModel):
    id: UUID
    gateway: str
    idempotency_key: str
    gateway_payment_ref: str | None
    amount_cents: int
    gateway_fee_cents: int | None
    status: str
    method: str | None
    card_last4: str | None
    failure_reason: str | None
    created_at: datetime


class PlatformCheckoutDetail(PlatformCheckout):
    order_list: list[CheckoutOrder]
    attempts: list[CheckoutAttempt]


class RetryResult(BaseModel):
    outcome: str
    checkout: PlatformCheckoutDetail


# --- audit log (phase 8) ---------------------------------------------------------------------

class AuditRow(BaseModel):
    id: int
    created_at: datetime
    tenant_id: UUID | None
    tenant_name: str | None
    actor_user_id: UUID | None
    actor_name: str | None
    action: str
    entity_type: str
    entity_id: UUID | None
    details: dict[str, Any] | None
    ip_address: str | None


class AuditPage(BaseModel):
    items: list[AuditRow]
    next_cursor: str | None
