"""Step 6: public catalogue, enrolment, the access rule, late-month requests, manual
grants, lesson playback with view limits."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from tests.conftest import AddMember, FakeBunny, FakeSms, Seed
from tests.helpers import auth_headers, error_code

Headers = dict[str, str]


@pytest.fixture
async def teacher(client: AsyncClient, sms: FakeSms, seed: Seed) -> Headers:
    return await auth_headers(client, sms, seed.a, seed.a.teacher_phone)


@pytest.fixture
async def student(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember) -> Headers:
    return await auth_headers(client, sms, seed.a, await members(seed.a, "student"))


async def member_id(client: AsyncClient, h: Headers) -> str:
    return (await client.get("/api/v1/auth/me", headers=h)).json()["member_id"]


async def monthly_class(client: AsyncClient, h: Headers, **overrides: Any) -> dict[str, Any]:
    """A published monthly class: Oct closed, Nov open, Dec upcoming; one live lesson per
    month, a free preview in October and one unpublished lesson."""
    body = {"title": "A/L Physics", "pricing_model": "monthly", "monthly_fee_cents": 200000, **overrides}
    c = (await client.post("/api/v1/org/classes", headers=h, json=body)).json()
    months = {}
    for month, status in (("2026-10-01", "closed"), ("2026-11-01", "open"), ("2026-12-01", "upcoming")):
        months[status] = (await client.post(f"/api/v1/org/classes/{c['id']}/months", headers=h,
                                            json={"month_start": month, "status": status})).json()
    lessons = {}
    for status, m in months.items():
        lessons[status] = (await client.post(f"/api/v1/org/classes/{c['id']}/lessons", headers=h, json={
            "class_month_id": m["id"], "title": f"Live {status}", "lesson_type": "live",
            "scheduled_at": "2026-11-03T14:00:00+05:30", "zoom_join_url": "https://zoom.us/j/111",
            "is_published": True})).json()
    lessons["preview"] = (await client.post(f"/api/v1/org/classes/{c['id']}/lessons", headers=h, json={
        "class_month_id": months["closed"]["id"], "title": "Intro", "lesson_type": "document",
        "is_published": True, "is_free_preview": True})).json()
    lessons["hidden"] = (await client.post(f"/api/v1/org/classes/{c['id']}/lessons", headers=h, json={
        "class_month_id": months["open"]["id"], "title": "Draft notes", "lesson_type": "document",
        "is_published": False})).json()
    await client.patch(f"/api/v1/org/classes/{c['id']}", headers=h, json={"status": "published"})
    return {"class": c, "months": months, "lessons": lessons}


def access_by_month(view: dict[str, Any]) -> dict[str, str]:
    return {m["month_start"]: m["access"] for m in view["months"]}


# --- public catalogue ---------------------------------------------------------------------

async def test_public_catalogue(client: AsyncClient, seed: Seed, teacher: Headers) -> None:
    k = await monthly_class(client, teacher)
    slug = k["class"]["slug"]
    anon = {"host": seed.a.host}

    listed = (await client.get("/api/v1/public/classes", headers=anon)).json()["items"]
    assert [c["slug"] for c in listed] == [slug]          # the seed's draft class is not listed
    assert listed[0]["teacher_name"] == "Teacher a" and listed[0]["currency"] == "LKR"

    detail = (await client.get(f"/api/v1/public/classes/{slug}", headers=anon)).json()
    assert [m["status"] for m in detail["months"]] == ["closed", "open", "upcoming"]
    assert detail["months"][0]["fee_cents"] == 200000
    titles = [lesson["title"] for lesson in detail["lessons"]]
    assert "Draft notes" not in titles and len(titles) == 4
    assert all("zoom_join_url" not in lesson for lesson in detail["lessons"])

    assert (await client.get("/api/v1/public/classes/physics", headers=anon)).status_code == 404  # draft
    in_b = {"host": seed.b.host}
    assert (await client.get(f"/api/v1/public/classes/{slug}", headers=in_b)).status_code == 404


# --- enrolment and the access rule ----------------------------------------------------------

async def test_student_view_before_access(client: AsyncClient, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    slug = k["class"]["slug"]
    view = (await client.get(f"/api/v1/student/classes/{slug}", headers=student)).json()
    assert view["enrolled"] is False

    view = (await client.post(f"/api/v1/student/classes/{slug}/enroll", headers=student)).json()
    assert view["enrolled"] is True
    assert access_by_month(view) == {"2026-10-01": "request", "2026-11-01": "buy", "2026-12-01": "upcoming"}
    unlocked = {lesson["title"]: lesson["unlocked"] for lesson in view["lessons"]}
    assert unlocked == {"Live closed": False, "Intro": True, "Live open": False, "Live upcoming": False}

    lesson = (await client.get(f"/api/v1/student/lessons/{k['lessons']['open']['id']}", headers=student)).json()
    assert lesson["unlocked"] is False and lesson["zoom_join_url"] is None and lesson["resources"] == []
    hidden = await client.get(f"/api/v1/student/lessons/{k['lessons']['hidden']['id']}", headers=student)
    assert hidden.status_code == 404

    mine = (await client.get("/api/v1/student/classes", headers=student)).json()
    assert [(c["class"]["slug"], c["unlocked_months"]) for c in mine] == [(slug, 0)]
    assert (await client.delete(f"/api/v1/student/classes/{slug}/enroll", headers=student)).status_code == 204
    assert (await client.get("/api/v1/student/classes", headers=student)).json() == []


async def test_free_class_unlocks_on_join(client: AsyncClient, teacher: Headers, student: Headers) -> None:
    c = (await client.post("/api/v1/org/classes", headers=teacher,
                           json={"title": "Free seminar", "pricing_model": "free"})).json()
    await client.post(f"/api/v1/org/classes/{c['id']}/lessons", headers=teacher,
                      json={"title": "Paper", "lesson_type": "document", "is_published": True})
    await client.patch(f"/api/v1/org/classes/{c['id']}", headers=teacher, json={"status": "published"})
    view = (await client.post(f"/api/v1/student/classes/{c['slug']}/enroll", headers=student)).json()
    assert view["has_class_access"] is True
    assert [lesson["unlocked"] for lesson in view["lessons"]] == [True]
    again = (await client.post(f"/api/v1/student/classes/{c['slug']}/enroll", headers=student)).json()
    assert again["has_class_access"] is True                    # joining twice: still one grant


# --- manual access (scholarships) ------------------------------------------------------------

async def test_manual_grant_unlocks_month(client: AsyncClient, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    cid, nov = k["class"]["id"], k["months"]["open"]["id"]
    sid = await member_id(client, student)

    resp = await client.post(f"/api/v1/org/classes/{cid}/grants", headers=teacher,
                             json={"student_member_id": sid, "class_month_id": nov, "source": "scholarship"})
    assert resp.status_code == 201
    grant = resp.json()
    dup = await client.post(f"/api/v1/org/classes/{cid}/grants", headers=teacher,
                            json={"student_member_id": sid, "class_month_id": nov})
    assert dup.status_code == 409 and error_code(dup) == "ALREADY_HAS_ACCESS"
    no_month = await client.post(f"/api/v1/org/classes/{cid}/grants", headers=teacher,
                                 json={"student_member_id": sid})
    assert error_code(no_month) == "MONTH_REQUIRED"
    teacher_id = await member_id(client, teacher)
    not_student = await client.post(f"/api/v1/org/classes/{cid}/grants", headers=teacher,
                                    json={"student_member_id": teacher_id, "class_month_id": nov})
    assert error_code(not_student) == "STUDENT_INVALID"

    view = (await client.get(f"/api/v1/student/classes/{k['class']['slug']}", headers=student)).json()
    assert view["enrolled"] is True                              # access implies membership
    assert access_by_month(view)["2026-11-01"] == "granted"
    lesson = (await client.get(f"/api/v1/student/lessons/{k['lessons']['open']['id']}", headers=student)).json()
    assert lesson["unlocked"] is True and lesson["zoom_join_url"] == "https://zoom.us/j/111"

    roster = (await client.get(f"/api/v1/org/classes/{cid}/students?month_id={nov}", headers=teacher)).json()
    assert [(r["member_id"], r["access"]["source"]) for r in roster] == [(sid, "scholarship")]
    roster_oct = (await client.get(f"/api/v1/org/classes/{cid}/students?month_id={k['months']['closed']['id']}",
                                   headers=teacher)).json()
    assert roster_oct[0]["access"] is None

    assert (await client.post(f"/api/v1/org/grants/{grant['id']}/revoke", headers=teacher,
                              json={"reason": "left the institute"})).status_code == 204
    again = await client.post(f"/api/v1/org/grants/{grant['id']}/revoke", headers=teacher, json={})
    assert error_code(again) == "ALREADY_REVOKED"
    lesson = (await client.get(f"/api/v1/student/lessons/{k['lessons']['open']['id']}", headers=student)).json()
    assert lesson["unlocked"] is False and lesson["zoom_join_url"] is None


async def test_expired_grant_gives_no_access(client: AsyncClient, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    sid = await member_id(client, student)
    grant = (await client.post(f"/api/v1/org/classes/{k['class']['id']}/grants", headers=teacher, json={
        "student_member_id": sid, "class_month_id": k["months"]["open"]["id"]})).json()
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE access_grants SET expires_at = now() - interval '1 day' WHERE id = :id"),
                        {"id": grant["id"]})
    lesson = (await client.get(f"/api/v1/student/lessons/{k['lessons']['open']['id']}", headers=student)).json()
    assert lesson["unlocked"] is False


# --- late-month requests ---------------------------------------------------------------------

async def test_late_month_requests(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember,
                                   teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    slug, oct_, nov = k["class"]["slug"], k["months"]["closed"]["id"], k["months"]["open"]["id"]

    resp = await client.post(f"/api/v1/student/months/{oct_}/late-request", headers=student, json={})
    assert resp.status_code == 409 and error_code(resp) == "NOT_ENROLLED"
    await client.post(f"/api/v1/student/classes/{slug}/enroll", headers=student)
    resp = await client.post(f"/api/v1/student/months/{nov}/late-request", headers=student, json={})
    assert error_code(resp) == "MONTH_NOT_CLOSED"
    resp = await client.post(f"/api/v1/student/months/{oct_}/late-request", headers=student,
                             json={"note": "I joined late"})
    assert resp.status_code == 201 and resp.json()["status"] == "pending"
    dup = await client.post(f"/api/v1/student/months/{oct_}/late-request", headers=student, json={})
    assert error_code(dup) == "REQUEST_EXISTS"
    view = (await client.get(f"/api/v1/student/classes/{slug}", headers=student)).json()
    assert access_by_month(view)["2026-10-01"] == "pending"

    # Only the class's teacher (or an owner/admin) sees and answers it.
    other = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    assert (await client.get("/api/v1/org/late-requests", headers=other)).json() == []
    inbox = (await client.get("/api/v1/org/late-requests", headers=teacher)).json()
    assert [(r["class_title"], r["month_start"], r["student_note"]) for r in inbox] == [
        ("A/L Physics", "2026-10-01", "I joined late")]
    rid = inbox[0]["id"]
    resp = await client.post(f"/api/v1/org/late-requests/{rid}/decision", headers=other, json={"decision": "approve"})
    assert resp.status_code == 404

    resp = await client.post(f"/api/v1/org/late-requests/{rid}/decision", headers=teacher,
                             json={"decision": "approve", "note": "OK"})
    assert resp.json()["status"] == "approved" and resp.json()["decided_at"]
    again = await client.post(f"/api/v1/org/late-requests/{rid}/decision", headers=teacher,
                              json={"decision": "reject"})
    assert error_code(again) == "REQUEST_DECIDED"
    view = (await client.get(f"/api/v1/student/classes/{slug}", headers=student)).json()
    assert access_by_month(view)["2026-10-01"] == "approved"   # may now pay for it (step 7)
    assert (await client.get("/api/v1/org/late-requests", headers=teacher)).json() == []
    assert len((await client.get("/api/v1/org/late-requests?status=approved", headers=teacher)).json()) == 1


async def test_rejected_request_cannot_be_repeated(client: AsyncClient, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher)
    await client.post(f"/api/v1/student/classes/{k['class']['slug']}/enroll", headers=student)
    oct_ = k["months"]["closed"]["id"]
    r = (await client.post(f"/api/v1/student/months/{oct_}/late-request", headers=student, json={})).json()
    await client.post(f"/api/v1/org/late-requests/{r['id']}/decision", headers=teacher, json={"decision": "reject"})
    view = (await client.get(f"/api/v1/student/classes/{k['class']['slug']}", headers=student)).json()
    assert access_by_month(view)["2026-10-01"] == "rejected"
    resp = await client.post(f"/api/v1/student/months/{oct_}/late-request", headers=student, json={})
    assert error_code(resp) == "REQUEST_REJECTED"


async def test_late_months_can_be_switched_off(client: AsyncClient, teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher, allow_late_months=False)
    view = (await client.post(f"/api/v1/student/classes/{k['class']['slug']}/enroll", headers=student)).json()
    assert access_by_month(view)["2026-10-01"] == "unavailable"
    resp = await client.post(f"/api/v1/student/months/{k['months']['closed']['id']}/late-request",
                             headers=student, json={})
    assert error_code(resp) == "LATE_MONTHS_NOT_ALLOWED"


# --- playback ------------------------------------------------------------------------------

async def test_open_files_and_view_limit(client: AsyncClient, seed: Seed, bunny: FakeBunny,
                                         teacher: Headers, student: Headers) -> None:
    k = await monthly_class(client, teacher, max_video_views=2)
    lesson_id = k["lessons"]["open"]["id"]
    video = (await client.post("/api/v1/org/media/videos", headers=teacher,
                               json={"filename": "rec.mp4", "size_bytes": 1000})).json()
    bunny.videos[video["upload"]["headers"]["VideoId"]]["status"] = 4
    await client.get(f"/api/v1/org/media/{video['media']['id']}", headers=teacher)      # sync -> ready
    pdf = (await client.post("/api/v1/org/media/documents", headers=teacher,
                             files={"file": ("t.pdf", b"%PDF-1.4 tute", "application/pdf")})).json()
    vres = (await client.post(f"/api/v1/org/lessons/{lesson_id}/resources", headers=teacher,
                              json={"media_asset_id": video["media"]["id"], "title": "Recording"})).json()
    dres = (await client.post(f"/api/v1/org/lessons/{lesson_id}/resources", headers=teacher,
                              json={"media_asset_id": pdf["id"], "is_downloadable": True})).json()

    locked = await client.post(f"/api/v1/student/resources/{vres['id']}/open", headers=student)
    assert locked.status_code == 403 and error_code(locked) == "ACCESS_DENIED"

    sid = await member_id(client, student)
    await client.post(f"/api/v1/org/classes/{k['class']['id']}/grants", headers=teacher,
                      json={"student_member_id": sid, "class_month_id": k["months"]["open"]["id"]})
    detail = (await client.get(f"/api/v1/student/lessons/{lesson_id}", headers=student)).json()
    assert [(r["title"], r["kind"], r["views_allowed"]) for r in detail["resources"]] == [
        ("Recording", "video", 2), ("t.pdf", "document", None)]

    first = (await client.post(f"/api/v1/student/resources/{vres['id']}/open", headers=student)).json()
    assert first["url"].startswith(f"https://iframe.mediadelivery.net/embed/{bunny.library_id}/")
    assert first["views_used"] == 1 and first["views_allowed"] == 2
    assert first["watermark"]["phone"].startswith("+9470")
    second = (await client.post(f"/api/v1/student/resources/{vres['id']}/open", headers=student)).json()
    assert second["views_used"] == 2
    third = await client.post(f"/api/v1/student/resources/{vres['id']}/open", headers=student)
    assert third.status_code == 403 and error_code(third) == "VIEW_LIMIT_REACHED"

    doc = (await client.post(f"/api/v1/student/resources/{dres['id']}/open", headers=student)).json()
    assert doc["url"].startswith("https://files.example.b-cdn.net/") and doc["views_used"] is None


async def test_archived_class_stays_open_for_students_with_access(client: AsyncClient, teacher: Headers,
                                                                  student: Headers, sms: FakeSms, seed: Seed,
                                                                  members: AddMember) -> None:
    k = await monthly_class(client, teacher)
    sid = await member_id(client, student)
    await client.post(f"/api/v1/org/classes/{k['class']['id']}/grants", headers=teacher,
                      json={"student_member_id": sid, "class_month_id": k["months"]["open"]["id"]})
    await client.patch(f"/api/v1/org/classes/{k['class']['id']}", headers=teacher, json={"status": "archived"})
    slug = k["class"]["slug"]
    assert (await client.get(f"/api/v1/student/classes/{slug}", headers=student)).status_code == 200
    assert (await client.get(f"/api/v1/public/classes/{slug}", headers={"host": seed.a.host})).status_code == 404
    stranger = await auth_headers(client, sms, seed.a, await members(seed.a, "student"))
    assert (await client.get(f"/api/v1/student/classes/{slug}", headers=stranger)).status_code == 404


# --- isolation (CLAUDE.md section 5, rule 8) ---------------------------------------------------

async def test_learning_tables_isolated(client: AsyncClient, seed: Seed, bunny: FakeBunny, teacher: Headers,
                                        student: Headers) -> None:
    k = await monthly_class(client, teacher)
    await client.post(f"/api/v1/student/classes/{k['class']['slug']}/enroll", headers=student)
    await client.post(f"/api/v1/student/months/{k['months']['closed']['id']}/late-request", headers=student, json={})
    sid = await member_id(client, student)
    await client.post(f"/api/v1/org/classes/{k['class']['id']}/grants", headers=teacher,
                      json={"student_member_id": sid, "class_month_id": k["months"]["open"]["id"]})
    pdf = (await client.post("/api/v1/org/media/documents", headers=teacher,
                             files={"file": ("t.pdf", b"%PDF-1.4", "application/pdf")})).json()
    res = (await client.post(f"/api/v1/org/lessons/{k['lessons']['open']['id']}/resources", headers=teacher,
                             json={"media_asset_id": pdf["id"]})).json()
    async with AdminSession() as s, s.begin():
        await s.execute(text("""INSERT INTO lesson_progress (tenant_id, student_member_id, lesson_resource_id)
                                VALUES (:t, :m, :r)"""), {"t": seed.a.id, "m": sid, "r": res["id"]})

    tables = ("class_enrollments", "late_month_requests", "access_grants", "lesson_progress")
    async with tenant_transaction(seed.b.id) as session:
        for table in tables:
            seen = (await session.execute(text(f"SELECT count(*) FROM {table} WHERE tenant_id = :a"),
                                          {"a": seed.a.id})).scalar_one()
            assert seen == 0, table
            touched = await session.execute(text(f"DELETE FROM {table} WHERE tenant_id = :a"), {"a": seed.a.id})
            assert touched.rowcount == 0, table  # type: ignore[attr-defined]
    async with AdminSession() as s:
        for table in tables:
            count = (await s.execute(text(f"SELECT count(*) FROM {table} WHERE tenant_id = :a"),
                                     {"a": seed.a.id})).scalar_one()
            assert count == 1, table
