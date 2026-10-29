import hmac
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.core.tenancy import TenantSession
from app.integrations.bunny import bunny_http
from app.modules.auth.dependencies import StaffActor
from app.modules.media import service
from app.modules.media.schemas import (
    MediaKind,
    MediaOut,
    MediaPage,
    PreviewOut,
    ResourceCreate,
    ResourceOut,
    VideoUploadCreate,
    VideoUploadOut,
)

Bunny = Annotated[httpx.AsyncClient, Depends(bunny_http)]

org_router = APIRouter(prefix="/org", tags=["org: media"])


@org_router.get("/media", response_model=MediaPage)
async def list_media(
    session: TenantSession, actor: StaffActor,
    kind: MediaKind | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> MediaPage:
    return await service.list_media(session, actor, kind=kind, cursor=cursor, limit=limit)


@org_router.post("/media/videos", response_model=VideoUploadOut, status_code=201)
async def create_video_upload(body: VideoUploadCreate, session: TenantSession, actor: StaffActor,
                              http: Bunny) -> VideoUploadOut:
    return await service.create_video_upload(session, actor, http, body)


@org_router.post("/media/documents", response_model=MediaOut, status_code=201)
async def upload_document(session: TenantSession, actor: StaffActor, http: Bunny,
                          file: Annotated[UploadFile, File()]) -> MediaOut:
    limit = get_settings().max_document_bytes
    content = await file.read(limit + 1)   # one byte over the limit is enough to refuse it
    return await service.upload_document(session, actor, http, file.filename or "document.pdf", content)


@org_router.get("/media/{asset_id}", response_model=MediaOut)
async def get_media(asset_id: UUID, session: TenantSession, actor: StaffActor, http: Bunny) -> MediaOut:
    return await service.get_media(session, actor, http, asset_id)


@org_router.delete("/media/{asset_id}", status_code=204)
async def delete_media(asset_id: UUID, session: TenantSession, actor: StaffActor, http: Bunny) -> Response:
    await service.delete_media(session, actor, http, asset_id)
    return Response(status_code=204)


@org_router.get("/media/{asset_id}/preview", response_model=PreviewOut)
async def preview_media(asset_id: UUID, session: TenantSession, actor: StaffActor) -> PreviewOut:
    return await service.preview(session, actor, asset_id)


@org_router.get("/lessons/{lesson_id}/resources", response_model=list[ResourceOut])
async def list_resources(lesson_id: UUID, session: TenantSession, actor: StaffActor) -> list[ResourceOut]:
    return await service.list_resources(session, actor, lesson_id)


@org_router.post("/lessons/{lesson_id}/resources", response_model=ResourceOut, status_code=201)
async def add_resource(lesson_id: UUID, body: ResourceCreate, session: TenantSession,
                       actor: StaffActor) -> ResourceOut:
    return await service.add_resource(session, actor, lesson_id, body)


@org_router.delete("/lesson-resources/{resource_id}", status_code=204)
async def remove_resource(resource_id: UUID, session: TenantSession, actor: StaffActor) -> Response:
    await service.remove_resource(session, actor, resource_id)
    return Response(status_code=204)


# --- Bunny webhook (no tenant host; see CLAUDE.md section 5) ----------------------------

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class StreamWebhook(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    library_id: int = Field(alias="VideoLibraryId")
    video_guid: str = Field(alias="VideoGuid", min_length=1, max_length=64)


@webhook_router.post("/bunny/stream")
async def bunny_stream_webhook(body: StreamWebhook, http: Bunny, token: str = "") -> dict[str, bool]:
    expected = get_settings().bunny_webhook_token
    if not expected or not hmac.compare_digest(token, expected):
        raise ApiError("NOT_FOUND", "Not found.", status_code=404)
    # The payload only says *which* video changed; its state is re-read from Bunny.
    handled = await service.handle_stream_webhook(http, body.library_id, body.video_guid)
    return {"ok": True, "handled": handled}
