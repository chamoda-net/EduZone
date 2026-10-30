from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl, field_validator


class SubjectRef(BaseModel):
    slug: str
    name: str


class SubjectOut(SubjectRef):
    id: UUID
    class_count: int
    teacher_count: int


class MarketClass(BaseModel):
    """A class card on the marketplace: public fields only."""

    id: UUID
    slug: str
    title: str
    exam: str | None
    batch_year: int | None
    medium: str | None
    cover_image_url: str | None
    pricing_model: str
    monthly_fee_cents: int | None
    one_time_price_cents: int | None
    currency: str
    subject_slug: str
    subject_name: str
    teacher_slug: str
    teacher_name: str
    teacher_photo_url: str | None
    org_slug: str
    org_name: str
    org_type: str
    open_month_start: date | None
    open_month_fee_cents: int | None
    has_live: bool
    has_recorded: bool
    has_free_preview: bool
    students: int
    path: str                            # /<subject>/<teacher>/<class>


class MarketClassPage(BaseModel):
    items: list[MarketClass]
    total: int
    next_cursor: str | None


class MarketMonth(BaseModel):
    id: UUID
    month_start: date
    status: str
    fee_cents: int | None
    currency: str


class MarketLesson(BaseModel):
    id: UUID
    class_month_id: UUID | None
    title: str
    lesson_type: str
    scheduled_at: datetime | None
    duration_minutes: int | None
    is_free_preview: bool


class TeacherCard(BaseModel):
    slug: str
    display_name: str
    headline: str | None
    photo_url: str | None


class MarketClassDetail(BaseModel):
    klass: MarketClass = Field(serialization_alias="class")
    description: str | None
    teacher: TeacherCard
    months: list[MarketMonth]
    lessons: list[MarketLesson]


class TeacherOut(BaseModel):
    slug: str
    display_name: str
    headline: str | None
    bio: str | None
    photo_url: str | None
    highlights: list[str]
    class_count: int
    students: int
    subjects: list[SubjectRef]
    mediums: list[str]


class TeacherPage(BaseModel):
    teacher: TeacherOut
    subject: SubjectRef | None           # the subject of this page (/<subject>/<teacher>)
    classes: list[MarketClass]
    other_subjects: list[SubjectRef]


class InstituteOut(BaseModel):
    slug: str
    name: str
    logo_url: str | None
    class_count: int
    teacher_count: int
    subjects: list[str]


class InstitutePage(BaseModel):
    institute: InstituteOut
    classes: list[MarketClass]


class SubjectPage(BaseModel):
    subject: SubjectOut
    classes: list[MarketClass]
    teachers: list[TeacherOut]


class Home(BaseModel):
    subjects: list[SubjectOut]
    popular: list[MarketClass]
    starting: list[MarketClass]          # an open month starting this month
    classes: int
    teachers: int


class SitemapOut(BaseModel):
    subjects: list[str]
    teachers: list[str]                  # /<subject>/<teacher>
    classes: list[str]
    institutes: list[str]


Sort = Literal["popular", "newest", "price"]
Format = Literal["live", "recorded"]


# --- the teacher's own profile (console) ------------------------------------------------

class ProfileOut(BaseModel):
    slug: str
    display_name: str
    headline: str | None
    bio: str | None
    photo_url: str | None
    highlights: list[str]
    public_paths: list[str]              # /<subject>/<slug> for every subject with a public class


class ProfileUpdate(BaseModel):
    model_config = {"extra": "forbid"}

    slug: str = Field(min_length=3, max_length=40)
    display_name: str = Field(min_length=1, max_length=80)
    headline: str | None = Field(default=None, max_length=120)
    bio: str | None = Field(default=None, max_length=2000)
    photo_url: HttpUrl | None = None
    highlights: list[str] = Field(default_factory=list, max_length=6)

    @field_validator("highlights")
    @classmethod
    def _clean(cls, v: list[str]) -> list[str]:
        items = [" ".join(h.split()) for h in v if h.strip()]
        if any(len(h) > 80 for h in items):
            raise ValueError("Keep each highlight under 80 characters.")
        return items

    @field_validator("slug")
    @classmethod
    def _lower(cls, v: str) -> str:
        return v.strip().lower()
