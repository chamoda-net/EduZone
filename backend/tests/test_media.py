"""Bunny integration (build step 5): video uploads, PDFs, webhook, signed URLs, lesson files.

Bunny itself is replaced by FakeBunny (an httpx MockTransport), so these tests need no
network and no Bunny account.
"""

import base64
import hashlib
import secrets
import time
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from app.integrations.bunny import signing
from tests.conftest import AddMember, FakeBunny, FakeSms, Seed
from tests.helpers import auth_headers, error_code

PDF = b"%PDF-1.4\n" + b"x" * 2000
Headers = dict[str, str]


@pytest.fixture
async def teacher(client: AsyncClient, sms: FakeSms, seed: Seed) -> Headers:
    return await auth_headers(client, sms, seed.a, seed.a.teacher_phone)


async def start_video(client: AsyncClient, h: Headers, size: int = 50_000_000) -> dict[str, Any]:
    resp = await client.post("/api/v1/org/media/videos", headers=h,
                             json={"filename": "Lesson 1.mp4", "size_bytes": size, "mime_type": "video/mp4"})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def upload_pdf(client: AsyncClient, h: Headers, content: bytes = PDF, name: str = "Tute 1.pdf") -> Any:
    return await client.post("/api/v1/org/media/documents", headers=h,
                             files={"file": (name, content, "application/pdf")})


async def make_lesson(client: AsyncClient, h: Headers, lesson_type: str) -> dict[str, Any]:
    c = (await client.post("/api/v1/org/classes", headers=h, json={
        "title": f"Class {secrets.token_hex(2)}", "pricing_model": "free"})).json()
    body: dict[str, Any] = {"title": "L", "lesson_type": lesson_type}
    if lesson_type == "live":
        body["scheduled_at"] = "2026-11-03T13:30:00+05:30"
    resp = await client.post(f"/api/v1/org/classes/{c['id']}/lessons", headers=h, json=body)
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- signatures ---------------------------------------------------------------------------

def test_signatures() -> None:
    assert signing.tus_signature(42, "key", 1700000000, "vid") == hashlib.sha256(b"42key1700000000vid").hexdigest()
    url = signing.embed_url("https://iframe.mediadelivery.net", 42, "vid", "tok", 1700000000)
    token = hashlib.sha256(b"tokvid1700000000").hexdigest()
    assert url == f"https://iframe.mediadelivery.net/embed/42/vid?token={token}&expires=1700000000"
    cdn = signing.cdn_url("files.b-cdn.net", "t/doc.pdf", "key", 1700000000)
    raw = hashlib.sha256(b"key/t/doc.pdf1700000000").digest()
    assert cdn == ("https://files.b-cdn.net/t/doc.pdf?token="
                   f"{base64.urlsafe_b64encode(raw).decode().rstrip('=')}&expires=1700000000")


# --- videos -------------------------------------------------------------------------------

async def test_video_upload_gets_tus_signature(client: AsyncClient, seed: Seed, bunny: FakeBunny,
                                               teacher: Headers) -> None:
    out = await start_video(client, teacher)
    lib = bunny.library_id
    guid = out["upload"]["headers"]["VideoId"]
    assert guid in bunny.videos and bunny.videos[guid]["title"] == "Lesson 1.mp4"
    h = out["upload"]["headers"]
    assert h["LibraryId"] == str(lib)
    assert int(h["AuthorizationExpire"]) > time.time() + 3600
    assert h["AuthorizationSignature"] == signing.tus_signature(lib, f"stream-key-{lib}",
                                                                int(h["AuthorizationExpire"]), guid)
    assert out["upload"]["endpoint"] == "https://video.bunnycdn.com/tusupload"
    assert out["media"]["status"] == "uploading" and out["media"]["kind"] == "video"


async def test_video_not_configured(client: AsyncClient, sms: FakeSms, seed: Seed, bunny: FakeBunny) -> None:
    in_b = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)  # tenant B has no library
    resp = await client.post("/api/v1/org/media/videos", headers=in_b,
                             json={"filename": "x.mp4", "size_bytes": 10})
    assert resp.status_code == 503 and error_code(resp) == "MEDIA_NOT_CONFIGURED"
    assert bunny.calls == []


async def test_video_limits(client: AsyncClient, seed: Seed, bunny: FakeBunny, teacher: Headers) -> None:
    resp = await client.post("/api/v1/org/media/videos", headers=teacher,
                             json={"filename": "x.mp4", "size_bytes": 11 * 1024**3})
    assert resp.status_code == 413 and error_code(resp) == "FILE_TOO_LARGE"

    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE tenants SET storage_limit_bytes = 100000000 WHERE id = :t"), {"t": seed.a.id})
    await start_video(client, teacher, size=60_000_000)
    resp = await client.post("/api/v1/org/media/videos", headers=teacher,
                             json={"filename": "y.mp4", "size_bytes": 60_000_000})
    assert resp.status_code == 409 and error_code(resp) == "STORAGE_LIMIT_REACHED"


async def test_status_syncs_from_bunny(client: AsyncClient, bunny: FakeBunny, teacher: Headers) -> None:
    out = await start_video(client, teacher)
    media_url = f"/api/v1/org/media/{out['media']['id']}"
    guid = out["upload"]["headers"]["VideoId"]

    bunny.videos[guid]["status"] = 3                       # transcoding
    assert (await client.get(media_url, headers=teacher)).json()["status"] == "processing"
    bunny.videos[guid].update(status=4, length=1800, storageSize=420_000_000)
    got = (await client.get(media_url, headers=teacher)).json()
    assert (got["status"], got["duration_seconds"], got["size_bytes"]) == ("ready", 1800, 420_000_000)

    bunny.down = True                                      # a Bunny outage doesn't break the page
    assert (await client.get(media_url, headers=teacher)).status_code == 200


async def test_webhook(client: AsyncClient, seed: Seed, bunny: FakeBunny, teacher: Headers) -> None:
    out = await start_video(client, teacher)
    guid = out["upload"]["headers"]["VideoId"]
    lib = bunny.library_id
    payload = {"VideoLibraryId": lib, "VideoGuid": guid, "Status": 3}

    resp = await client.post("/api/v1/webhooks/bunny/stream?token=wrong", json=payload)
    assert resp.status_code == 404
    bunny.videos[guid].update(status=4, length=60)
    # Webhooks arrive without a tenant host.
    resp = await client.post("/api/v1/webhooks/bunny/stream?token=hook-secret", json=payload,
                             headers={"host": "api.internal"})
    assert resp.json() == {"ok": True, "handled": True}
    async with AdminSession() as s:
        status = (await s.execute(text("SELECT status FROM media_assets WHERE external_id = :g"),
                                  {"g": guid})).scalar_one()
    assert status == "ready"

    resp = await client.post("/api/v1/webhooks/bunny/stream?token=hook-secret",
                             json={**payload, "VideoLibraryId": 1})
    assert resp.json()["handled"] is False


# --- documents ----------------------------------------------------------------------------

async def test_pdf_upload(client: AsyncClient, seed: Seed, bunny: FakeBunny, teacher: Headers) -> None:
    resp = await upload_pdf(client, teacher, name="../../Unit 1 tute.pdf")
    assert resp.status_code == 201, resp.text
    media = resp.json()
    assert media["status"] == "ready" and media["size_bytes"] == len(PDF) and media["name"] == "../../Unit 1 tute.pdf"
    [(path, content)] = bunny.files.items()
    assert path == f"{seed.a.id}/documents/{media['id']}/Unit-1-tute.pdf"   # tenant folder, safe name
    assert content == PDF


async def test_pdf_rules(client: AsyncClient, bunny: FakeBunny, teacher: Headers) -> None:
    resp = await upload_pdf(client, teacher, content=b"MZ\x90\x00 not a pdf")
    assert resp.status_code == 415 and error_code(resp) == "FILE_TYPE_NOT_ALLOWED"
    settings = get_settings()
    saved, settings.max_document_bytes = settings.max_document_bytes, 1000
    try:
        resp = await upload_pdf(client, teacher)
    finally:
        settings.max_document_bytes = saved
    assert resp.status_code == 413
    settings.bunny_storage_zone = None
    resp = await upload_pdf(client, teacher)
    assert resp.status_code == 503 and error_code(resp) == "MEDIA_NOT_CONFIGURED"
    assert bunny.files == {}


# --- preview, listing, permissions, delete ------------------------------------------------

async def test_preview_urls(client: AsyncClient, bunny: FakeBunny, teacher: Headers) -> None:
    out = await start_video(client, teacher)
    vid = out["media"]["id"]
    resp = await client.get(f"/api/v1/org/media/{vid}/preview", headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "MEDIA_NOT_READY"

    bunny.videos[out["upload"]["headers"]["VideoId"]]["status"] = 4
    await client.get(f"/api/v1/org/media/{vid}", headers=teacher)          # sync to ready
    url = (await client.get(f"/api/v1/org/media/{vid}/preview", headers=teacher)).json()["url"]
    assert url.startswith(f"https://iframe.mediadelivery.net/embed/{bunny.library_id}/")
    assert "token=" in url and "expires=" in url

    doc = (await upload_pdf(client, teacher)).json()
    url = (await client.get(f"/api/v1/org/media/{doc['id']}/preview", headers=teacher)).json()["url"]
    assert url.startswith("https://files.example.b-cdn.net/") and "token=" in url


async def test_teachers_see_their_own_files(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember,
                                            bunny: FakeBunny, teacher: Headers) -> None:
    other = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    mine = (await upload_pdf(client, teacher)).json()
    theirs = (await upload_pdf(client, other)).json()

    listed = (await client.get("/api/v1/org/media", headers=teacher)).json()["items"]
    assert [m["id"] for m in listed] == [mine["id"]]
    assert (await client.get(f"/api/v1/org/media/{theirs['id']}", headers=teacher)).status_code == 404
    everything = (await client.get("/api/v1/org/media?kind=document", headers=owner)).json()["items"]
    assert {m["id"] for m in everything} == {mine["id"], theirs["id"]}

    in_b = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    assert (await client.get(f"/api/v1/org/media/{mine['id']}", headers=in_b)).status_code == 404


async def test_delete_media(client: AsyncClient, bunny: FakeBunny, teacher: Headers) -> None:
    out = await start_video(client, teacher)
    guid = out["upload"]["headers"]["VideoId"]
    lesson = await make_lesson(client, teacher, "recorded")
    resource = (await client.post(f"/api/v1/org/lessons/{lesson['id']}/resources", headers=teacher,
                                  json={"media_asset_id": out["media"]["id"]})).json()

    media_url = f"/api/v1/org/media/{out['media']['id']}"
    resp = await client.delete(media_url, headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "IN_USE"
    assert (await client.delete(f"/api/v1/org/lesson-resources/{resource['id']}", headers=teacher)).status_code == 204
    assert (await client.delete(media_url, headers=teacher)).status_code == 204
    assert guid not in bunny.videos
    assert (await client.get(media_url, headers=teacher)).status_code == 404
    assert (await client.get("/api/v1/org/media", headers=teacher)).json()["items"] == []


# --- lesson files -------------------------------------------------------------------------

async def test_lesson_files(client: AsyncClient, sms: FakeSms, seed: Seed, bunny: FakeBunny,
                            teacher: Headers) -> None:
    video = (await start_video(client, teacher))["media"]
    pdf = (await upload_pdf(client, teacher)).json()
    tute = await make_lesson(client, teacher, "document")
    live = await make_lesson(client, teacher, "live")

    resp = await client.post(f"/api/v1/org/lessons/{tute['id']}/resources", headers=teacher,
                             json={"media_asset_id": video["id"]})
    assert resp.status_code == 400 and error_code(resp) == "MEDIA_KIND_INVALID"

    # A live lesson can get its recording and a tute; videos are never downloadable.
    rec = await client.post(f"/api/v1/org/lessons/{live['id']}/resources", headers=teacher,
                            json={"media_asset_id": video["id"], "title": "Recording", "is_downloadable": True})
    assert rec.status_code == 201 and rec.json()["is_downloadable"] is False
    doc = await client.post(f"/api/v1/org/lessons/{live['id']}/resources", headers=teacher,
                            json={"media_asset_id": pdf["id"], "is_downloadable": True})
    assert doc.json()["is_downloadable"] is True and doc.json()["sort_order"] == 2
    dup = await client.post(f"/api/v1/org/lessons/{live['id']}/resources", headers=teacher,
                            json={"media_asset_id": pdf["id"]})
    assert dup.status_code == 409 and error_code(dup) == "ALREADY_ATTACHED"

    listed = (await client.get(f"/api/v1/org/lessons/{live['id']}/resources", headers=teacher)).json()
    assert [(r["title"], r["media"]["kind"]) for r in listed] == [("Recording", "video"), (None, "document")]

    # Another tenant can't attach this tenant's file, or see the lesson's files.
    in_b = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    b_lesson = await make_lesson(client, in_b, "document")
    resp = await client.post(f"/api/v1/org/lessons/{b_lesson['id']}/resources", headers=in_b,
                             json={"media_asset_id": pdf["id"]})
    assert resp.status_code == 404
    assert (await client.get(f"/api/v1/org/lessons/{live['id']}/resources", headers=in_b)).status_code == 404


# --- isolation (CLAUDE.md section 5, rule 8) ----------------------------------------------

async def test_media_tables_isolated(client: AsyncClient, sms: FakeSms, seed: Seed, bunny: FakeBunny,
                                     teacher: Headers) -> None:
    lesson = await make_lesson(client, teacher, "document")
    pdf = (await upload_pdf(client, teacher)).json()
    await client.post(f"/api/v1/org/lessons/{lesson['id']}/resources", headers=teacher,
                      json={"media_asset_id": pdf["id"]})
    async with tenant_transaction(seed.b.id) as session:
        for table in ("media_assets", "lesson_resources"):
            seen = (await session.execute(text(f"SELECT count(*) FROM {table} WHERE tenant_id = :a"),
                                          {"a": seed.a.id})).scalar_one()
            assert seen == 0, table
        touched = await session.execute(text("UPDATE media_assets SET status = 'deleted' WHERE id = :id"),
                                        {"id": pdf["id"]})
    assert touched.rowcount == 0  # type: ignore[attr-defined]
