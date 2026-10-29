from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, FetchedValue
from sqlalchemy.orm import Mapped, mapped_column

from app.core.models import Base


class MediaAsset(Base):
    __tablename__ = "media_assets"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    uploaded_by: Mapped[UUID]                 # tenant_members.id
    kind: Mapped[str]                         # video | document | image
    provider: Mapped[str]                     # bunny_stream | bunny_storage
    external_id: Mapped[str]                  # Stream video GUID, or storage path
    original_filename: Mapped[str | None]
    mime_type: Mapped[str | None]
    size_bytes: Mapped[int]
    duration_seconds: Mapped[int | None]
    status: Mapped[str]                       # uploading | processing | ready | failed | deleted
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())


class LessonResource(Base):
    __tablename__ = "lesson_resources"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    lesson_id: Mapped[UUID]
    media_asset_id: Mapped[UUID]
    title: Mapped[str | None]
    sort_order: Mapped[int]
    is_downloadable: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=FetchedValue())
