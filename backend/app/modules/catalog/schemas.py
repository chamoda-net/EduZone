from datetime import date, datetime
from typing import Annotated, ClassVar, Literal, Self
from urllib.parse import urlparse
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Exam = Literal["grade_5", "ol", "al", "other"]
Medium = Literal["si", "ta", "en"]
PricingModel = Literal["monthly", "one_time", "free"]
ClassStatus = Literal["draft", "published", "archived"]
MonthStatus = Literal["upcoming", "open", "closed"]
LessonType = Literal["live", "recorded", "document"]

Cents = Annotated[int, Field(ge=0, le=10**12)]


def _https_url(v: str) -> str:
    parsed = urlparse(v)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("must be an https:// URL")
    return v


HttpsUrl = Annotated[str, Field(max_length=1000), AfterValidator(_https_url)]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=80)]


def _first_of_month(v: date) -> date:
    if v.day != 1:
        raise ValueError("must be the first day of a month, e.g. 2026-11-01")
    return v


MonthStart = Annotated[date, AfterValidator(_first_of_month)]


class _Patch(BaseModel):
    """Partial update: only fields the client sent are applied. Fields listed in
    `non_nullable` may be omitted but never set to null."""

    model_config = ConfigDict(extra="forbid")
    non_nullable: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _no_null_required(self) -> Self:
        for name in self.non_nullable:
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

    def changes(self) -> dict[str, object]:
        return self.model_dump(exclude_unset=True)


# --- classes ------------------------------------------------------------------------

class ClassCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    slug: Slug | None = None                    # generated from the title when omitted
    description: str | None = Field(default=None, max_length=5000)
    subject: str | None = Field(default=None, max_length=100)
    subject_id: UUID | None = None              # an EduZone subject; sets `subject` to its name
    exam: Exam | None = None
    batch_year: int | None = Field(default=None, ge=2000, le=2100)
    medium: Medium | None = None
    cover_image_url: HttpsUrl | None = None
    pricing_model: PricingModel
    monthly_fee_cents: Cents | None = None
    one_time_price_cents: Cents | None = None
    allow_late_months: bool = True
    max_video_views: int | None = Field(default=None, ge=1, le=1000)
    teacher_member_id: UUID | None = None       # defaults to the caller


class ClassUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = (
        "title", "slug", "pricing_model", "allow_late_months", "status", "teacher_member_id",
    )

    title: str | None = Field(default=None, min_length=1, max_length=200)
    slug: Slug | None = None
    description: str | None = Field(default=None, max_length=5000)
    subject: str | None = Field(default=None, max_length=100)
    subject_id: UUID | None = None
    exam: Exam | None = None
    batch_year: int | None = Field(default=None, ge=2000, le=2100)
    medium: Medium | None = None
    cover_image_url: HttpsUrl | None = None
    pricing_model: PricingModel | None = None
    monthly_fee_cents: Cents | None = None
    one_time_price_cents: Cents | None = None
    allow_late_months: bool | None = None
    max_video_views: int | None = Field(default=None, ge=1, le=1000)
    status: ClassStatus | None = None
    teacher_member_id: UUID | None = None


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    teacher_member_id: UUID
    title: str
    slug: str
    description: str | None
    subject: str | None
    subject_id: UUID | None
    exam: str | None
    batch_year: int | None
    medium: str | None
    cover_image_url: str | None
    pricing_model: str
    monthly_fee_cents: int | None
    one_time_price_cents: int | None
    currency: str
    allow_late_months: bool
    max_video_views: int | None
    status: str
    created_at: datetime
    updated_at: datetime


class ClassPage(BaseModel):
    items: list[ClassOut]
    next_cursor: str | None


# --- months ---------------------------------------------------------------------------

class MonthCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month_start: MonthStart
    fee_cents: Cents | None = None              # NULL = the class's monthly fee
    status: MonthStatus = "open"


class MonthUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = ("status",)

    fee_cents: Cents | None = None
    status: MonthStatus | None = None


class MonthOut(BaseModel):
    id: UUID
    class_id: UUID
    month_start: date
    fee_cents: int | None
    effective_fee_cents: int
    currency: str
    status: str
    created_at: datetime


# --- lessons --------------------------------------------------------------------------

class LessonCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_month_id: UUID | None = None          # required for monthly classes, else must be null
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    lesson_type: LessonType
    sort_order: int = Field(default=0, ge=0, le=100_000)
    scheduled_at: AwareDatetime | None = None   # required for live lessons
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    zoom_join_url: HttpsUrl | None = None       # live lessons only
    is_free_preview: bool = False
    is_published: bool = False


class LessonUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = (
        "title", "lesson_type", "sort_order", "is_free_preview", "is_published",
    )

    class_month_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    lesson_type: LessonType | None = None
    sort_order: int | None = Field(default=None, ge=0, le=100_000)
    scheduled_at: AwareDatetime | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    zoom_join_url: HttpsUrl | None = None
    is_free_preview: bool | None = None
    is_published: bool | None = None


class LessonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    class_id: UUID
    class_month_id: UUID | None
    title: str
    description: str | None
    lesson_type: str
    sort_order: int
    scheduled_at: datetime | None
    duration_minutes: int | None
    zoom_join_url: str | None                   # staff view; students get it only after the access check
    is_free_preview: bool
    is_published: bool
    created_at: datetime
    updated_at: datetime
