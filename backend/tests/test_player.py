"""Phase 7: our own player. Signed HLS playlists (or Bunny's iframe when a library has no CDN keys), resume
points and completion, reported by the player and checked against the access rule every time."""

import base64
import hashlib
from typing import Any
from urllib.parse import unquote

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import BunnyLibraryKeys, get_settings
from app.core.db import AdminSession
from app.integrations.bunny import signing
from tests.conftest import AddMember, FakeBunny, FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_learning import member_id, monthly_class

Headers = dict[str, str]


def test_hls_url_signs_the_video_directory() -> None:
    url = signing.hls_url("vz-abc.b-cdn.net", "vid-123", "secret", 1900000000)
    assert url.startswith("https://vz-abc.b-cdn.net/bcdn_token=")
    assert url.endswith("&expires=1900000000&token_path=%2Fvid-123%2F/vid-123/playlist.m3u8")
    token = url.split("bcdn_token=", 1)[1].split("&", 1)[0]
    expected = base64.urlsafe_b64encode(hashlib.sha256(
        b"secret/vid-123/1900000000token_path=/vid-123/").digest()).decode().rstrip("=")
    assert token == expected
    assert unquote(url.split("token_path=", 1)[1].split("/vid-123/playlist", 1)[0]) == "/vid-123/"
    # Another video, another expiry or another key gives another token.
    assert signing.hls_url("vz-abc.b-cdn.net", "vid-124", "secret", 1900000000) != url
    assert signing.hls_url("vz-abc.b-cdn.net", "vid-123", "other", 1900000000) != url


@pytest.fixture
async def teacher(client: AsyncClient, sms: FakeSms, seed: Seed) -> Headers:
    return await auth_headers(client, sms, seed.a, seed.a.teacher_phone)


@pytest.fixture
async def student(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember) -> Headers:
    return await auth_headers(client, sms, seed.a, await members(seed.a, "student"))


@pytest.fixture
async def lesson_video(client: AsyncClient, bunny: FakeBunny, teacher: Headers, student: Headers) -> dict[str, Any]:
    """A ready 10-minute recording on November's lesson, and the student holds November."""
    k = await monthly_class(client, teacher)
    lesson_id = k["lessons"]["open"]["id"]
    video = (await client.post("/api/v1/org/media/videos", headers=teacher,
                               json={"filename": "rec.mp4", "size_bytes": 1000})).json()
    bunny.videos[video["upload"]["headers"]["VideoId"]]["status"] = 4
    await client.get(f"/api/v1/org/media/{video['media']['id']}", headers=teacher)      # sync -> ready
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE media_assets SET duration_seconds = 600 WHERE id = :id"),
                        {"id": video["media"]["id"]})
    res = (await client.post(f"/api/v1/org/lessons/{lesson_id}/resources", headers=teacher,
                             json={"media_asset_id": video["media"]["id"], "title": "Recording"})).json()
    sid = await member_id(client, student)
    await client.post(f"/api/v1/org/classes/{k['class']['id']}/grants", headers=teacher,
                      json={"student_member_id": sid, "class_month_id": k["months"]["open"]["id"]})
    return {"k": k, "lesson_id": lesson_id, "resource_id": res["id"], "video_id": video["upload"]["headers"]["VideoId"]}


async def open_video(client: AsyncClient, h: Headers, resource_id: str) -> Any:
    return await client.post(f"/api/v1/learn/resources/{resource_id}/open", headers=h)


async def report(client: AsyncClient, h: Headers, resource_id: str, position: int, watched: int = 15) -> Any:
    return await client.post(f"/api/v1/learn/resources/{resource_id}/progress", headers=h,
                             json={"position_seconds": position, "watched_seconds": watched})


async def test_hls_when_the_library_has_cdn_keys(client: AsyncClient, bunny: FakeBunny, student: Headers,
                                                 lesson_video: dict[str, Any]) -> None:
    embed = (await open_video(client, student, lesson_video["resource_id"])).json()
    assert embed["playback"] == "embed" and embed["url"].startswith("https://iframe.mediadelivery.net/embed/")

    settings = get_settings()
    lib = str(bunny.library_id)
    keys = settings.bunny_stream_libraries[lib]
    settings.bunny_stream_libraries = {**settings.bunny_stream_libraries, lib: BunnyLibraryKeys(
        api_key=keys.api_key, token_key=keys.token_key, cdn_host="vz-test.b-cdn.net", cdn_token_key="cdn-secret")}
    hls = (await open_video(client, student, lesson_video["resource_id"])).json()
    assert hls["playback"] == "hls" and hls["duration_seconds"] == 600
    assert hls["url"].startswith("https://vz-test.b-cdn.net/bcdn_token=")
    assert hls["url"].endswith(f"/{lesson_video['video_id']}/playlist.m3u8")
    assert hls["views_used"] == 2                         # every play session still counts a view


async def test_dev_stream_stands_in_locally(client: AsyncClient, student: Headers, lesson_video: dict[str, Any],
                                            monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "dev_video_stream_url", "https://test-streams.example/demo.m3u8")
    opened = (await open_video(client, student, lesson_video["resource_id"])).json()
    assert (opened["playback"], opened["url"]) == ("hls", "https://test-streams.example/demo.m3u8")
    monkeypatch.setattr(settings, "environment", "production")
    assert (await open_video(client, student, lesson_video["resource_id"])).json()["playback"] == "embed"


async def test_progress_resume_and_completion(client: AsyncClient, student: Headers,
                                              lesson_video: dict[str, Any]) -> None:
    rid = lesson_video["resource_id"]
    early = await report(client, student, rid, 30)
    assert early.status_code == 409 and error_code(early) == "PLAY_NOT_STARTED"   # no play session yet

    assert (await open_video(client, student, rid)).json()["resume_at_seconds"] == 0
    saved = (await report(client, student, rid, 120)).json()
    assert saved == {"position_seconds": 120, "watched_seconds": 15, "completed": False}
    # The lesson page and the next play pick up where they stopped.
    detail = (await client.get(f"/api/v1/learn/lessons/{lesson_video['lesson_id']}", headers=student)).json()
    assert [(r["position_seconds"], r["completed"]) for r in detail["resources"]] == [(120, False)]
    assert (await open_video(client, student, rid)).json()["resume_at_seconds"] == 120

    # A big claimed watch time counts at most 60 s; positions past the end are clamped.
    assert (await report(client, student, rid, 200, watched=120)).json()["watched_seconds"] == 75
    done = (await report(client, student, rid, 5000)).json()
    assert done["position_seconds"] == 600 and done["completed"]
    assert (await open_video(client, student, rid)).json()["resume_at_seconds"] == 0   # finished: start over
    # Completion is never undone by rewinding.
    assert (await report(client, student, rid, 10)).json()["completed"]


async def test_progress_follows_the_access_rule(client: AsyncClient, seed: Seed, sms: FakeSms, members: AddMember,
                                                teacher: Headers, student: Headers,
                                                lesson_video: dict[str, Any]) -> None:
    rid = lesson_video["resource_id"]
    await open_video(client, student, rid)
    # Another student of the same organization without November: refused, and nothing of ours changes.
    other = await auth_headers(client, sms, seed.a, await members(seed.a, "student"))
    locked = await report(client, other, rid, 300)
    assert locked.status_code in (403, 404)
    detail = (await client.get(f"/api/v1/learn/lessons/{lesson_video['lesson_id']}", headers=student)).json()
    assert detail["resources"][0]["position_seconds"] == 0
    # Unknown resources and bad input.
    assert (await report(client, student, "00000000-0000-0000-0000-000000000000", 1)).status_code == 404
    assert (await client.post(f"/api/v1/learn/resources/{rid}/progress", headers=student,
                              json={"position_seconds": -1, "watched_seconds": 1})).status_code == 422
