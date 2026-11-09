from datetime import datetime
from typing import Annotated, ClassVar, Literal
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.modules.catalog.schemas import Cents, HttpsUrl, Medium, Slug, _Patch
from app.modules.learning.schemas import StudentResource

Level = Literal["beginner", "intermediate", "advanced", "all"]
CoursePricing = Literal["one_time", "free"]
LectureType = Literal["recorded", "document", "article"]
CourseStatus = Literal["draft", "in_review", "published", "archived"]


def _clean_list(v: list[str]) -> list[str]:
    """Trimmed, non-empty, no duplicates, order kept."""
    seen: list[str] = []
    for item in (x.strip() for x in v):
        if item and item not in seen:
            seen.append(item)
    return seen


ShortList = Annotated[list[Annotated[str, Field(max_length=160)]], Field(max_length=20), AfterValidator(_clean_list)]


# --- course -----------------------------------------------------------------------------

class CourseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=120)
    category_id: int | None = None
    teacher_member_id: UUID | None = None        # defaults to the caller; owners/admins may pick another


class CourseUpdate(_Patch):
    """Landing page, intended learners, pricing and messages. Status changes have their own actions."""

    non_nullable: ClassVar[tuple[str, ...]] = (
        "title", "slug", "pricing_model", "learning_objectives", "requirements", "target_audience",
        "teacher_member_id",
    )

    title: str | None = Field(default=None, min_length=3, max_length=120)
    slug: Slug | None = None
    subtitle: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=20000)
    category_id: int | None = None
    level: Level | None = None
    medium: Medium | None = None                 # the course language
    cover_image_url: HttpsUrl | None = None
    promo_media_id: UUID | None = None
    subject_id: UUID | None = None               # optional link to a school subject (exam-skills courses)
    learning_objectives: ShortList | None = None
    requirements: ShortList | None = None
    target_audience: ShortList | None = None
    pricing_model: CoursePricing | None = None
    one_time_price_cents: Cents | None = None
    welcome_message: str | None = Field(default=None, max_length=1000)
    completion_message: str | None = Field(default=None, max_length=1000)
    teacher_member_id: UUID | None = None


class Check(BaseModel):
    key: str                                     # e.g. "objectives"; the UI has a message for each
    ok: bool
    current: int | None = None                   # how many there are now (lectures, minutes, words, items)
    required: int | None = None


class CourseRow(BaseModel):
    id: UUID
    title: str
    slug: str
    subtitle: str | None
    status: str
    pricing_model: str
    one_time_price_cents: int | None
    currency: str
    category_id: int | None
    cover_image_url: str | None
    teacher_member_id: UUID
    teacher_name: str
    lecture_count: int
    total_video_seconds: int
    review_note: str | None
    submitted_at: datetime | None
    first_published_at: datetime | None
    created_at: datetime
    updated_at: datetime


class LectureOut(BaseModel):
    id: UUID
    section_id: UUID
    title: str
    description: str | None
    lesson_type: str
    article_body: str | None
    sort_order: int
    is_free_preview: bool
    is_published: bool
    video_seconds: int                           # ready videos attached to it
    files: int                                   # attached videos and PDFs
    pending_videos: int                          # attached videos not ready yet


class SectionOut(BaseModel):
    id: UUID
    title: str
    sort_order: int
    lectures: list[LectureOut]


class CourseDetail(CourseRow):
    description: str | None
    level: str | None
    medium: str | None
    subject_id: UUID | None
    promo_media_id: UUID | None
    learning_objectives: list[str]
    requirements: list[str]
    target_audience: list[str]
    welcome_message: str | None
    completion_message: str | None
    sections: list[SectionOut]
    checks: list[Check]
    ready_to_submit: bool
    needs_review: bool                           # true until EduZone approves the first publish
    wishlist_count: int = 0                      # students who saved it (step C5; never who)
    tenant_name: str | None = None               # set in the platform admin's view


# --- curriculum ---------------------------------------------------------------------------

class SectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    sort_order: int | None = Field(default=None, ge=0, le=100_000)   # default: after the last one


class SectionUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = ("title", "sort_order")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    sort_order: int | None = Field(default=None, ge=0, le=100_000)


class LectureCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    lesson_type: LectureType
    description: str | None = Field(default=None, max_length=5000)
    article_body: str | None = Field(default=None, max_length=50000)
    sort_order: int | None = Field(default=None, ge=0, le=100_000)
    is_free_preview: bool = False
    is_published: bool = True


class LectureUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = (
        "title", "lesson_type", "sort_order", "is_free_preview", "is_published", "section_id",
    )

    section_id: UUID | None = None               # move to another section of the same course
    title: str | None = Field(default=None, min_length=1, max_length=200)
    lesson_type: LectureType | None = None
    description: str | None = Field(default=None, max_length=5000)
    article_body: str | None = Field(default=None, max_length=50000)
    sort_order: int | None = Field(default=None, ge=0, le=100_000)
    is_free_preview: bool | None = None
    is_published: bool | None = None


class CategoryOut(BaseModel):
    id: int
    parent_id: int | None
    slug: str
    name_en: str
    name_si: str | None
    name_ta: str | None
    sort_order: int
    is_active: bool


# --- staff review (platform admin) ------------------------------------------------------------

class ReviewRow(BaseModel):
    id: UUID
    tenant_id: UUID
    tenant_name: str
    title: str
    teacher_name: str
    category_name: str | None
    lecture_count: int
    total_video_seconds: int
    pricing_model: str
    one_time_price_cents: int | None
    currency: str
    submitted_at: datetime | None


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "request_changes"]
    note: str | None = Field(default=None, max_length=2000)


class UnpublishIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=3, max_length=2000)


class CategoryCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slug: Annotated[str, Field(pattern=r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])$")]
    name_en: str = Field(min_length=2, max_length=60)
    name_si: str | None = Field(default=None, max_length=60)
    name_ta: str | None = Field(default=None, max_length=60)
    parent_id: int | None = None
    sort_order: int = Field(default=0, ge=0, le=10000)


class CategoryUpdate(_Patch):
    non_nullable: ClassVar[tuple[str, ...]] = ("name_en", "sort_order", "is_active")

    # The slug is a public URL (/courses/<slug>) and stays fixed; so does the parent.
    name_en: str | None = Field(default=None, min_length=2, max_length=60)
    name_si: str | None = Field(default=None, max_length=60)
    name_ta: str | None = Field(default=None, max_length=60)
    sort_order: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None


# --- the student side (step C3: buying, the player, progress) ----------------------------------

class CourseProgress(BaseModel):
    completed: int
    total: int                                   # published lectures
    percent: int                                 # 0-100, rounded down (100 only when all are done)


class LearnLecture(BaseModel):
    id: UUID
    title: str
    lesson_type: str
    video_seconds: int
    is_free_preview: bool
    unlocked: bool
    completed: bool


class LearnSection(BaseModel):
    id: UUID
    title: str
    lectures: list[LearnLecture]
    completed: int
    total: int


class LearnCourse(BaseModel):
    id: UUID
    slug: str
    title: str
    subtitle: str | None
    cover_image_url: str | None
    status: str
    path: str                                    # the marketplace page, /course/<slug>
    teacher_name: str
    teacher_slug: str | None
    org_name: str
    pricing_model: str
    one_time_price_cents: int | None
    currency: str
    has_access: bool                             # bought, enrolled for free, or given by the teacher
    welcome_message: str | None                  # shown to students who have access
    completion_message: str | None               # shown once the course is complete
    progress: CourseProgress
    sections: list[LearnSection]
    next_lecture_id: UUID | None                 # where "Continue" goes: the first lecture not done yet
    my_rating: int | None = None                 # the student's own review, if any (step C4)
    certificate_no: str | None = None            # issued at 100% of a paid course (step C4)


class LectureDetail(BaseModel):
    id: UUID
    course_id: UUID
    section_title: str
    title: str
    lesson_type: str
    description: str | None                      # only when unlocked
    article_body: str | None                     # Markdown, only when unlocked
    unlocked: bool
    completed: bool
    resources: list[StudentResource]
    prev_id: UUID | None
    next_id: UUID | None


class CompletionOut(BaseModel):
    lecture_id: UUID
    completed: bool
    progress: CourseProgress


class MyCourse(BaseModel):
    id: UUID
    slug: str
    title: str
    cover_image_url: str | None
    teacher_name: str
    org_name: str
    progress: CourseProgress
    next_lecture_id: UUID | None
    started_at: datetime                         # when access began
    last_activity_at: datetime | None


# --- reviews and certificates (step C4) ----------------------------------------------------------

class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class MyReview(BaseModel):
    id: UUID
    rating: int
    comment: str | None
    status: str                                  # visible | hidden (by EduZone staff)
    instructor_reply: str | None
    replied_at: datetime | None
    created_at: datetime
    updated_at: datetime


class PublicReview(BaseModel):
    id: UUID
    rating: int
    comment: str | None
    reviewer: str                                # first name and initial only
    instructor_reply: str | None
    replied_at: datetime | None
    created_at: datetime


class ReviewSummary(BaseModel):
    average: float | None
    count: int
    distribution: dict[int, int]                 # stars -> number of reviews, 5 to 1


class PublicReviewPage(BaseModel):
    summary: ReviewSummary
    items: list[PublicReview]
    next_cursor: str | None


class StaffReview(BaseModel):
    """The instructor's and EduZone staff's view of a review."""

    id: UUID
    course_id: UUID
    course_title: str
    rating: int
    comment: str | None
    reviewer: str
    status: str
    hidden_reason: str | None
    instructor_reply: str | None
    replied_at: datetime | None
    created_at: datetime
    tenant_name: str | None = None               # in the platform admin's list


class ReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply: str | None = Field(default=None, max_length=2000)   # empty or null removes the reply


class HideIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=500)


class CertificateOut(BaseModel):
    certificate_no: str
    course_id: UUID
    course_title: str
    student_name: str
    instructor_name: str
    org_name: str
    total_video_seconds: int
    issued_at: datetime
    revoked_at: datetime | None
    verify_path: str                             # /certificates/<no>


class CertificateVerify(BaseModel):
    certificate_no: str
    student_name: str
    course_title: str
    instructor_name: str
    org_name: str
    total_video_seconds: int
    issued_at: datetime
    revoked_at: datetime | None
    valid: bool
