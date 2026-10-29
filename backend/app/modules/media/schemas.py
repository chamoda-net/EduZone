from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MediaKind = Literal["video", "document"]


class MediaOut(BaseModel):
    id: UUID
    kind: str
    name: str                     # the uploaded file's name
    mime_type: str | None
    size_bytes: int
    duration_seconds: int | None
    status: str                   # uploading | processing | ready | failed
    created_at: datetime


class MediaPage(BaseModel):
    items: list[MediaOut]
    next_cursor: str | None


class VideoUploadCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    filename: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(gt=0)              # checked against the storage limit up front
    mime_type: str | None = Field(default=None, max_length=100)


class TusUpload(BaseModel):
    """Everything the browser needs to upload straight to Bunny with tus-js-client."""

    endpoint: str
    headers: dict[str, str]                    # AuthorizationSignature, AuthorizationExpire, VideoId, LibraryId
    expires_at: datetime


class VideoUploadOut(BaseModel):
    media: MediaOut
    upload: TusUpload


class PreviewOut(BaseModel):
    url: str                                   # short-lived, signed
    expires_at: datetime


class ResourceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    media_asset_id: UUID
    title: str | None = Field(default=None, max_length=200)
    is_downloadable: bool = False


class ResourceOut(BaseModel):
    id: UUID
    lesson_id: UUID
    title: str | None
    sort_order: int
    is_downloadable: bool
    media: MediaOut
