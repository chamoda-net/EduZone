from datetime import date, datetime
from typing import Annotated, ClassVar, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.auth.phone import normalize_phone
from app.modules.catalog.schemas import _Patch

OrgType = Literal["individual", "institute", "corporate"]
TenantStatus = Literal["pending", "active", "suspended", "closed"]
FeeBearer = Literal["tenant", "platform"]

# Subdomains no organization can take.
RESERVED_SLUGS = frozenset({
    "admin", "api", "www", "app", "learn", "teach", "t", "login", "register", "support", "status", "mail",
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
    owner_phone: str = Field(max_length=32)
    owner_name: str = Field(min_length=1, max_length=120)

    @field_validator("owner_phone")
    @classmethod
    def _phone(cls, v: str) -> str:
        return normalize_phone(v)


class TenantUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = ("name", "status", "commission_bps", "gateway_fee_bearer")

    name: str | None = Field(default=None, min_length=2, max_length=120)
    status: TenantStatus | None = None
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
