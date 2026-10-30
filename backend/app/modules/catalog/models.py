from datetime import date, datetime
from uuid import UUID

from sqlalchemy import DateTime, FetchedValue, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base


class ClassModel(Base):
    __tablename__ = "classes"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    teacher_member_id: Mapped[UUID]
    title: Mapped[str]
    slug: Mapped[str]
    description: Mapped[str | None]
    subject: Mapped[str | None]
    subject_id: Mapped[UUID | None]
    exam: Mapped[str | None]
    batch_year: Mapped[int | None] = mapped_column(SmallInteger)
    medium: Mapped[str | None]
    cover_image_url: Mapped[str | None]
    pricing_model: Mapped[str]
    monthly_fee_cents: Mapped[int | None]
    one_time_price_cents: Mapped[int | None]
    allow_late_months: Mapped[bool]
    max_video_views: Mapped[int | None] = mapped_column(SmallInteger)
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())


class ClassMonth(Base):
    __tablename__ = "class_months"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    class_id: Mapped[UUID]
    month_start: Mapped[date]
    fee_cents: Mapped[int | None]
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())


class Lesson(Base):
    __tablename__ = "lessons"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    class_id: Mapped[UUID]
    class_month_id: Mapped[UUID | None]
    title: Mapped[str]
    description: Mapped[str | None]
    lesson_type: Mapped[str]
    sort_order: Mapped[int]
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int | None] = mapped_column(SmallInteger)
    zoom_join_url: Mapped[str | None]
    is_free_preview: Mapped[bool]
    is_published: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
