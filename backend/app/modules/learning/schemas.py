"""Student-facing shapes. Never include zoom links, media URLs or other students' data
unless the access rule has passed for that lesson."""

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PublicClass(BaseModel):
    id: UUID
    slug: str
    title: str
    description: str | None
    subject: str | None
    exam: str | None
    batch_year: int | None
    medium: str | None
    cover_image_url: str | None
    pricing_model: str
    monthly_fee_cents: int | None
    one_time_price_cents: int | None
    currency: str
    teacher_name: str


class PublicClassPage(BaseModel):
    items: list[PublicClass]
    next_cursor: str | None


class PublicMonth(BaseModel):
    id: UUID
    month_start: date
    fee_cents: int                       # effective fee for the month
    currency: str
    status: str                          # upcoming | open | closed


class PublicLesson(BaseModel):
    id: UUID
    class_month_id: UUID | None
    title: str
    lesson_type: str
    sort_order: int
    scheduled_at: datetime | None
    duration_minutes: int | None
    is_free_preview: bool


class PublicClassDetail(BaseModel):
    klass: PublicClass = Field(serialization_alias="class")
    months: list[PublicMonth]
    lessons: list[PublicLesson]


# What a student may do about a month, from their point of view.
MonthAccess = Literal[
    "granted",       # active access grant
    "buy",           # open month, can pay now (payments arrive in step 7)
    "upcoming",      # not open yet
    "request",       # closed month: may ask the teacher
    "pending",       # request waiting for the teacher
    "approved",      # teacher approved: can pay for it
    "rejected",      # teacher said no
    "unavailable",   # closed and the class doesn't allow late months
]


class StudentMonth(PublicMonth):
    access: MonthAccess


class StudentLesson(PublicLesson):
    unlocked: bool


class StudentClassView(BaseModel):
    klass: PublicClass = Field(serialization_alias="class")
    enrolled: bool
    has_class_access: bool               # one-time / free classes: a class-level grant
    months: list[StudentMonth]
    lessons: list[StudentLesson]


class MyClass(BaseModel):
    klass: PublicClass = Field(serialization_alias="class")
    enrolled_at: datetime
    unlocked_months: int


class LateRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str | None = Field(default=None, max_length=500)


class LateRequestOut(BaseModel):
    id: UUID
    class_month_id: UUID
    status: str
    student_note: str | None
    decision_note: str | None
    created_at: datetime


class StudentResource(BaseModel):
    id: UUID
    title: str
    kind: str                            # video | document
    duration_seconds: int | None
    is_downloadable: bool
    ready: bool
    views_used: int
    views_allowed: int | None            # NULL = unlimited


class StudentLessonDetail(StudentLesson):
    class_id: UUID
    class_slug: str
    class_title: str
    description: str | None
    zoom_join_url: str | None            # only after the access check
    resources: list[StudentResource]


class Watermark(BaseModel):
    name: str
    phone: str | None


class OpenResourceOut(BaseModel):
    kind: str
    url: str                             # signed, short-lived
    expires_at: datetime
    watermark: Watermark
    views_used: int | None = None
    views_allowed: int | None = None


# --- organization console --------------------------------------------------------------

class GrantInfo(BaseModel):
    id: UUID
    source: str                          # purchase | manual | free | scholarship
    granted_at: datetime


class ClassStudent(BaseModel):
    member_id: UUID
    full_name: str
    phone: str | None
    enrollment_status: str | None        # active | left | removed (None: access without joining)
    enrolled_at: datetime | None
    access: GrantInfo | None             # for the month asked about (or the class, if not monthly)


class GrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    student_member_id: UUID
    class_month_id: UUID | None = None   # required for monthly classes
    source: Literal["manual", "scholarship"] = "manual"


class GrantRevoke(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=300)


class LateRequestRow(BaseModel):
    id: UUID
    status: str
    student_member_id: UUID
    student_name: str
    student_phone: str | None
    class_id: UUID
    class_title: str
    class_month_id: UUID
    month_start: date
    student_note: str | None
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None


class LateRequestDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=500)
