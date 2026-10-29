"""Videos (Bunny Stream) and PDFs (Bunny Storage) for the organization console.

Videos: we create the Bunny video and a media_assets row ('uploading'), then the browser
uploads straight to Bunny with a short-lived TUS signature. Bunny's webhook (or a status
sync when staff look at the file) moves it to processing -> ready / failed.
PDFs: small enough to pass through the API; stored under /<tenant_id>/documents/...

Permissions follow the catalogue: owners and admins see every file; teachers see the
files they uploaded. Anything else is a 404.
"""

import re
import time
import uuid
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.pagination import decode_cursor, encode_cursor
from app.core.tenancy import tenant_transaction
from app.integrations.bunny import not_configured, signing, storage_client, stream_client
from app.integrations.bunny.stream import video_status
from app.modules.auth.dependencies import Actor
from app.modules.catalog.service import load_lesson
from app.modules.media import repository as repo
from app.modules.media.models import LessonResource, MediaAsset
from app.modules.media.schemas import (
    MediaOut,
    MediaPage,
    PreviewOut,
    ResourceCreate,
    ResourceOut,
    TusUpload,
    VideoUploadCreate,
    VideoUploadOut,
)

_PENDING = ("uploading", "processing")


def _not_found() -> ApiError:
    return ApiError("NOT_FOUND", "File not found.", status_code=404)


def media_out(m: MediaAsset) -> MediaOut:
    return MediaOut(
        id=m.id, kind=m.kind, name=m.original_filename or "file", mime_type=m.mime_type,
        size_bytes=m.size_bytes, duration_seconds=m.duration_seconds, status=m.status, created_at=m.created_at,
    )


async def _audit(session: AsyncSession, actor: Actor, action: str, entity_type: str, entity_id: UUID,
                 details: dict[str, object] | None = None) -> None:
    await write_audit(session, actor_user_id=actor.auth.user_id, action=action, entity_type=entity_type,
                      entity_id=entity_id, details=details, ip=actor.ip)


async def _load_asset(session: AsyncSession, actor: Actor, asset_id: UUID, *, for_update: bool = False) -> MediaAsset:
    m = await repo.get_asset(session, asset_id, for_update=for_update)
    if m is None or not (actor.manages_all or m.uploaded_by == actor.auth.member_id):
        raise _not_found()
    return m


async def _check_quota(session: AsyncSession, limit: int | None, extra_bytes: int) -> None:
    """Plan limit (CLAUDE.md section 9): block new uploads once storage would exceed it."""
    if limit is not None and await repo.stored_bytes(session) + extra_bytes > limit:
        raise ApiError("STORAGE_LIMIT_REACHED",
                       "Your storage limit is reached. Delete unused files or contact EduZone.", status_code=409)


def _safe_filename(name: str, default_ext: str) -> str:
    base = re.sub(r"[^A-Za-z0-9._-]+", "-", name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]).strip("-.")[:100]
    base = base or "file"
    return base if base.lower().endswith(default_ext) else f"{base}{default_ext}"


# --- videos ---------------------------------------------------------------------------

async def create_video_upload(session: AsyncSession, actor: Actor, http: httpx.AsyncClient,
                              body: VideoUploadCreate) -> VideoUploadOut:
    s = get_settings()
    if body.size_bytes > s.max_video_bytes:
        raise ApiError("FILE_TOO_LARGE", f"Videos can be at most {s.max_video_bytes // 1024**3} GB.", 413)
    tenant = await repo.tenant_media_settings(session)
    stream, library_id, _ = stream_client(http, tenant.bunny_library_id)
    await _check_quota(session, tenant.storage_limit_bytes, body.size_bytes)

    guid = await stream.create_video(body.filename)
    m = await repo.insert_asset(session, {
        "uploaded_by": actor.auth.member_id, "kind": "video", "provider": "bunny_stream", "external_id": guid,
        "original_filename": body.filename, "mime_type": body.mime_type, "size_bytes": body.size_bytes,
        "status": "uploading",
    })
    await _audit(session, actor, "media.create", "media_asset", m.id, {"kind": "video", "name": body.filename})

    expires = int(time.time()) + s.upload_signature_ttl_seconds
    keys = s.bunny_stream_libraries[str(library_id)]
    upload = TusUpload(
        endpoint=s.bunny_stream_tus_endpoint,
        headers={
            "AuthorizationSignature": signing.tus_signature(library_id, keys.api_key, expires, guid),
            "AuthorizationExpire": str(expires),
            "VideoId": guid,
            "LibraryId": str(library_id),
        },
        expires_at=datetime.fromtimestamp(expires, UTC),
    )
    return VideoUploadOut(media=media_out(m), upload=upload)


async def _sync_video(session: AsyncSession, http: httpx.AsyncClient, m: MediaAsset,
                      library_id: int | None) -> MediaAsset:
    """Ask Bunny for the video's real state (webhook payloads are never trusted as-is)."""
    stream, _, _ = stream_client(http, library_id)
    video = await stream.get_video(m.external_id)
    values: dict[str, object] = {"status": "failed"} if video is None else {"status": video_status(video.status)}
    if video is not None and video.length_seconds:
        values["duration_seconds"] = video.length_seconds
    if video is not None and video.storage_size:
        values["size_bytes"] = video.storage_size
    if all(getattr(m, k) == v for k, v in values.items()):
        return m
    return await repo.update_asset(session, m.id, values)


async def handle_stream_webhook(http: httpx.AsyncClient, library_id: int, guid: str) -> bool:
    """Bunny calls this when a video changes state. Returns False when we don't know the video."""
    async with AppSession() as session:
        tenant_id = await repo.resolve_library_tenant(session, library_id)
    if tenant_id is None:
        return False
    async with tenant_transaction(tenant_id) as session:
        m = await repo.get_video_by_guid(session, guid)
        if m is None or m.status == "deleted":
            return False
        await _sync_video(session, http, m, library_id)
    return True


# --- documents ------------------------------------------------------------------------

async def upload_document(session: AsyncSession, actor: Actor, http: httpx.AsyncClient,
                          filename: str, content: bytes) -> MediaOut:
    s = get_settings()
    if len(content) > s.max_document_bytes:
        raise ApiError("FILE_TOO_LARGE", f"PDFs can be at most {s.max_document_bytes // 1024**2} MB.", 413)
    if not content.startswith(b"%PDF-"):
        raise ApiError("FILE_TYPE_NOT_ALLOWED", "Only PDF files can be uploaded.", 415)
    storage = storage_client(http)
    tenant = await repo.tenant_media_settings(session)
    await _check_quota(session, tenant.storage_limit_bytes, len(content))

    asset_id = uuid.uuid4()
    name = _safe_filename(filename, ".pdf")
    path = f"{tenant.id}/documents/{asset_id}/{name}"
    await storage.upload(path, content, "application/pdf")
    m = await repo.insert_asset(session, {
        "id": asset_id, "uploaded_by": actor.auth.member_id, "kind": "document", "provider": "bunny_storage",
        "external_id": path, "original_filename": filename[:200], "mime_type": "application/pdf",
        "size_bytes": len(content), "status": "ready",
    })
    await _audit(session, actor, "media.create", "media_asset", m.id, {"kind": "document", "name": filename})
    return media_out(m)


# --- library --------------------------------------------------------------------------

async def list_media(session: AsyncSession, actor: Actor, *, kind: str | None, cursor: str | None,
                     limit: int) -> MediaPage:
    rows = await repo.list_assets(
        session,
        uploaded_by=None if actor.manages_all else actor.auth.member_id,
        kind=kind,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    page = rows[:limit]
    return MediaPage(
        items=[media_out(m) for m in page],
        next_cursor=encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
    )


async def get_media(session: AsyncSession, actor: Actor, http: httpx.AsyncClient, asset_id: UUID) -> MediaOut:
    m = await _load_asset(session, actor, asset_id, for_update=True)
    if m.kind == "video" and m.status in _PENDING:
        # Covers missed webhooks and local development, where Bunny can't reach us.
        tenant = await repo.tenant_media_settings(session)
        try:
            m = await _sync_video(session, http, m, tenant.bunny_library_id)
        except ApiError:
            pass  # show the last known state rather than failing the page
    return media_out(m)


async def delete_media(session: AsyncSession, actor: Actor, http: httpx.AsyncClient, asset_id: UUID) -> None:
    m = await _load_asset(session, actor, asset_id, for_update=True)
    if await repo.asset_in_use(session, m.id):
        raise ApiError("IN_USE", "This file is attached to a lesson. Remove it from the lesson first.", 409)
    if m.provider == "bunny_stream":
        tenant = await repo.tenant_media_settings(session)
        stream, _, _ = stream_client(http, tenant.bunny_library_id)
        await stream.delete_video(m.external_id)
    else:
        await storage_client(http).delete(m.external_id)
    # Keep the row (audit trail, history); it no longer counts towards storage.
    await repo.update_asset(session, m.id, {"status": "deleted"})
    await _audit(session, actor, "media.delete", "media_asset", m.id, {"name": m.original_filename})


async def preview(session: AsyncSession, actor: Actor, asset_id: UUID) -> PreviewOut:
    """Short-lived signed URL so staff can check a file. Students get theirs only after
    the access check (step 6)."""
    m = await _load_asset(session, actor, asset_id)
    return await signed_url(session, m)


async def signed_url(session: AsyncSession, m: MediaAsset) -> PreviewOut:
    """Signed playback/download URL for a file. Callers do the access check first."""
    s = get_settings()
    if m.kind == "video":
        if m.status != "ready":
            raise ApiError("MEDIA_NOT_READY", "This video is still processing.", 409)
        library_id = (await repo.tenant_media_settings(session)).bunny_library_id
        keys = s.bunny_stream_libraries.get(str(library_id)) if library_id is not None else None
        if library_id is None or keys is None:
            raise not_configured("Video")
        expires = int(time.time()) + s.video_url_ttl_seconds
        url = signing.embed_url(s.bunny_stream_embed_base, library_id, m.external_id, keys.token_key, expires)
    else:
        if not (s.bunny_cdn_host and s.bunny_cdn_token_key):
            raise not_configured("File storage")
        expires = int(time.time()) + s.document_url_ttl_seconds
        url = signing.cdn_url(s.bunny_cdn_host, m.external_id, s.bunny_cdn_token_key, expires)
    return PreviewOut(url=url, expires_at=datetime.fromtimestamp(expires, UTC))


# --- lesson files ---------------------------------------------------------------------

def _resource_out(r: LessonResource, m: MediaAsset) -> ResourceOut:
    return ResourceOut(id=r.id, lesson_id=r.lesson_id, title=r.title, sort_order=r.sort_order,
                       is_downloadable=r.is_downloadable, media=media_out(m))


async def list_resources(session: AsyncSession, actor: Actor, lesson_id: UUID) -> list[ResourceOut]:
    lesson, _ = await load_lesson(session, actor, lesson_id)
    return [_resource_out(r, m) for r, m in await repo.list_resources(session, lesson.id)]


async def add_resource(session: AsyncSession, actor: Actor, lesson_id: UUID, body: ResourceCreate) -> ResourceOut:
    lesson, _ = await load_lesson(session, actor, lesson_id)
    m = await _load_asset(session, actor, body.media_asset_id)
    if m.status == "failed":
        raise ApiError("MEDIA_FAILED", "This file failed to process. Upload it again.", 409)
    if m.kind == "video" and lesson.lesson_type == "document":
        raise ApiError("MEDIA_KIND_INVALID", "A tute lesson can only have PDF files.")
    if m.kind not in ("video", "document"):
        raise ApiError("MEDIA_KIND_INVALID", "Only videos and PDFs can be attached to lessons.")
    if await repo.resource_exists(session, lesson.id, m.id):
        raise ApiError("ALREADY_ATTACHED", "This file is already attached to the lesson.", 409)
    r = await repo.insert_resource(session, {
        "lesson_id": lesson.id, "media_asset_id": m.id, "title": body.title,
        # Videos are never downloadable; that would defeat signed, view-limited playback.
        "is_downloadable": body.is_downloadable and m.kind == "document",
    })
    await _audit(session, actor, "lesson_resource.create", "lesson_resource", r.id,
                 {"lesson_id": lesson.id, "media_asset_id": m.id})
    return _resource_out(r, m)


async def remove_resource(session: AsyncSession, actor: Actor, resource_id: UUID) -> None:
    r = await repo.get_resource(session, resource_id)
    if r is None:
        raise ApiError("NOT_FOUND", "Lesson file not found.", status_code=404)
    try:
        await load_lesson(session, actor, r.lesson_id)
    except ApiError:
        raise ApiError("NOT_FOUND", "Lesson file not found.", status_code=404) from None
    await repo.delete_resource(session, r.id)
    await _audit(session, actor, "lesson_resource.delete", "lesson_resource", r.id,
                 {"lesson_id": r.lesson_id, "media_asset_id": r.media_asset_id})
