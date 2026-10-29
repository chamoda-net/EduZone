"""Organization console: classes, months, lessons (build step 4)."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from tests.conftest import AddMember, FakeSms, Seed
from tests.helpers import auth_headers, error_code

Headers = dict[str, str]
MONTHLY = {"title": "2027 A/L Physics - Theory", "pricing_model": "monthly", "monthly_fee_cents": 200000}


async def create_class(client: AsyncClient, h: Headers, **overrides: Any) -> dict[str, Any]:
    resp = await client.post("/api/v1/org/classes", json={**MONTHLY, **overrides}, headers=h)
    assert resp.status_code == 201, resp.text
    return resp.json()


async def create_month(client: AsyncClient, h: Headers, class_id: str, month: str = "2026-11-01",
                       **extra: Any) -> dict[str, Any]:
    resp = await client.post(f"/api/v1/org/classes/{class_id}/months", json={"month_start": month, **extra},
                             headers=h)
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
async def teacher(client: AsyncClient, sms: FakeSms, seed: Seed) -> Headers:
    return await auth_headers(client, sms, seed.a, seed.a.teacher_phone)


@pytest.fixture
async def owner(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember) -> Headers:
    return await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))


# --- access -----------------------------------------------------------------------------

async def test_requires_sign_in(client: AsyncClient, seed: Seed) -> None:
    resp = await client.get("/api/v1/org/classes", headers={"host": seed.a.host})
    assert resp.status_code == 401


async def test_students_are_refused(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember) -> None:
    h = await auth_headers(client, sms, seed.a, await members(seed.a, "student"))
    resp = await client.get("/api/v1/org/classes", headers=h)
    assert resp.status_code == 403
    assert error_code(resp) == "ACCESS_DENIED"


async def test_teacher_sees_only_own_classes(client: AsyncClient, sms: FakeSms, seed: Seed,
                                             members: AddMember, teacher: Headers, owner: Headers) -> None:
    other = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    mine = await create_class(client, teacher, title="Mine")
    theirs = await create_class(client, other, title="Theirs")

    seeded = str(seed.a.class_id)  # the seed's own class, taught by teacher A
    listed = (await client.get("/api/v1/org/classes", headers=teacher)).json()["items"]
    assert {c["id"] for c in listed} == {mine["id"], seeded}
    assert (await client.get(f"/api/v1/org/classes/{theirs['id']}", headers=teacher)).status_code == 404
    resp = await client.patch(f"/api/v1/org/classes/{theirs['id']}", json={"title": "x"}, headers=teacher)
    assert resp.status_code == 404

    everything = (await client.get("/api/v1/org/classes", headers=owner)).json()["items"]
    assert {c["id"] for c in everything} == {mine["id"], theirs["id"], seeded}


async def test_other_tenants_ids_are_not_found(client: AsyncClient, sms: FakeSms, seed: Seed,
                                               teacher: Headers) -> None:
    c = await create_class(client, teacher)
    m = await create_month(client, teacher, c["id"])
    in_b = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    assert (await client.get(f"/api/v1/org/classes/{c['id']}", headers=in_b)).status_code == 404
    assert (await client.patch(f"/api/v1/org/months/{m['id']}", json={"status": "closed"},
                               headers=in_b)).status_code == 404


# --- classes ------------------------------------------------------------------------------

async def test_create_class(client: AsyncClient, seed: Seed, teacher: Headers) -> None:
    c = await create_class(client, teacher)
    assert c["slug"] == "2027-a-l-physics-theory"
    assert c["teacher_member_id"] == str(seed.a.member_id)
    assert c["status"] == "draft"
    assert c["monthly_fee_cents"] == 200000 and c["currency"] == "LKR"

    async with AdminSession() as s:
        row = (await s.execute(text("SELECT action, actor_user_id IS NOT NULL AS has_actor, tenant_id "
                                    "FROM audit_logs WHERE entity_id = :id"), {"id": c["id"]})).one()
    assert row.action == "class.create" and row.has_actor and row.tenant_id == seed.a.id


@pytest.mark.parametrize("body", [
    {"title": "x", "pricing_model": "monthly"},
    {"title": "x", "pricing_model": "one_time"},
])
async def test_pricing_needs_a_price(client: AsyncClient, teacher: Headers, body: dict[str, Any]) -> None:
    resp = await client.post("/api/v1/org/classes", json=body, headers=teacher)
    assert resp.status_code == 400
    assert error_code(resp) == "PRICING_INVALID"


async def test_slugs(client: AsyncClient, teacher: Headers) -> None:
    first = await create_class(client, teacher, title="Chemistry")
    second = await create_class(client, teacher, title="Chemistry")
    assert first["slug"] == "chemistry"
    assert second["slug"].startswith("chemistry-") and second["slug"] != "chemistry"
    resp = await client.post("/api/v1/org/classes", json={**MONTHLY, "slug": "chemistry"}, headers=teacher)
    assert resp.status_code == 409
    assert error_code(resp) == "SLUG_TAKEN"
    sinhala = await create_class(client, teacher, title="භෞතික විද්‍යාව")
    assert sinhala["slug"].startswith("class")


async def test_assigning_teachers(client: AsyncClient, seed: Seed, members: AddMember, sms: FakeSms,
                                  teacher: Headers, owner: Headers) -> None:
    await members(seed.a, "teacher")
    async with AdminSession() as s:
        other_teacher = (await s.execute(text(
            "SELECT id FROM tenant_members WHERE tenant_id = :t AND role = 'teacher' AND id <> :me"
        ), {"t": seed.a.id, "me": seed.a.member_id})).scalar_one()
    await members(seed.a, "student")
    async with AdminSession() as s:
        student = (await s.execute(text(
            "SELECT id FROM tenant_members WHERE tenant_id = :t AND role = 'student'"), {"t": seed.a.id})).scalar_one()

    resp = await client.post("/api/v1/org/classes", json={**MONTHLY, "teacher_member_id": str(other_teacher)},
                             headers=teacher)
    assert resp.status_code == 403
    c = await create_class(client, owner, teacher_member_id=str(other_teacher))
    assert c["teacher_member_id"] == str(other_teacher)

    for bad in (student, seed.b.member_id):
        resp = await client.post("/api/v1/org/classes", json={**MONTHLY, "teacher_member_id": str(bad)},
                                 headers=owner)
        assert resp.status_code == 400
        assert error_code(resp) == "TEACHER_INVALID"

    resp = await client.patch(f"/api/v1/org/classes/{c['id']}",
                              json={"teacher_member_id": str(seed.a.member_id)}, headers=owner)
    assert resp.json()["teacher_member_id"] == str(seed.a.member_id)


async def test_status_flow_and_pricing_lock(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher)
    url = f"/api/v1/org/classes/{c['id']}"

    resp = await client.patch(url, json={"pricing_model": "one_time", "one_time_price_cents": 500000},
                              headers=teacher)
    assert resp.status_code == 200 and resp.json()["pricing_model"] == "one_time"

    assert (await client.patch(url, json={"status": "published"}, headers=teacher)).json()["status"] == "published"
    resp = await client.patch(url, json={"status": "draft"}, headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "STATUS_INVALID"
    resp = await client.patch(url, json={"pricing_model": "free"}, headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "PRICING_LOCKED"
    resp = await client.delete(url, headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "CLASS_NOT_DRAFT"
    assert (await client.patch(url, json={"status": "archived"}, headers=teacher)).status_code == 200

    async with AdminSession() as s:
        actions = (await s.execute(text("SELECT action FROM audit_logs WHERE entity_id = :id ORDER BY id"),
                                   {"id": c["id"]})).scalars().all()
    assert actions == ["class.create", "class.update", "class.publish", "class.archive"]


async def test_pricing_locked_once_class_has_months(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher)
    await create_month(client, teacher, c["id"])
    resp = await client.patch(f"/api/v1/org/classes/{c['id']}",
                              json={"pricing_model": "free"}, headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "PRICING_LOCKED"


async def test_required_fields_cannot_be_nulled(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher)
    resp = await client.patch(f"/api/v1/org/classes/{c['id']}", json={"title": None}, headers=teacher)
    assert resp.status_code == 422
    resp = await client.patch(f"/api/v1/org/classes/{c['id']}", json={"bogus": 1}, headers=teacher)
    assert resp.status_code == 422
    # Optional fields can be cleared.
    resp = await client.patch(f"/api/v1/org/classes/{c['id']}", json={"subject": "Physics"}, headers=teacher)
    resp = await client.patch(f"/api/v1/org/classes/{c['id']}", json={"subject": None}, headers=teacher)
    assert resp.json()["subject"] is None


async def test_delete_draft_class(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher)
    m = await create_month(client, teacher, c["id"])
    assert (await client.delete(f"/api/v1/org/classes/{c['id']}", headers=teacher)).status_code == 204
    assert (await client.get(f"/api/v1/org/classes/{c['id']}", headers=teacher)).status_code == 404
    assert (await client.patch(f"/api/v1/org/months/{m['id']}", json={"status": "closed"},
                               headers=teacher)).status_code == 404


async def test_delete_blocked_by_access_grants(client: AsyncClient, seed: Seed, members: AddMember,
                                               teacher: Headers) -> None:
    c = await create_class(client, teacher)
    m = await create_month(client, teacher, c["id"])
    await members(seed.a, "student")
    async with AdminSession() as s, s.begin():
        await s.execute(text("""
            INSERT INTO access_grants (tenant_id, student_member_id, class_id, class_month_id, source)
            SELECT :t, id, :c, :m, 'manual' FROM tenant_members WHERE tenant_id = :t AND role = 'student'
        """), {"t": seed.a.id, "c": c["id"], "m": m["id"]})
    resp = await client.delete(f"/api/v1/org/months/{m['id']}", headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "IN_USE"
    resp = await client.delete(f"/api/v1/org/classes/{c['id']}", headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "IN_USE"
    # The failed delete left the class intact.
    assert (await client.get(f"/api/v1/org/classes/{c['id']}", headers=teacher)).status_code == 200


async def test_pagination(client: AsyncClient, seed: Seed, teacher: Headers) -> None:
    assert (await client.delete(f"/api/v1/org/classes/{seed.a.class_id}", headers=teacher)).status_code == 204
    ids = [(await create_class(client, teacher, title=f"Class {i}"))["id"] for i in range(3)]
    first = (await client.get("/api/v1/org/classes?limit=2", headers=teacher)).json()
    assert [c["id"] for c in first["items"]] == ids[::-1][:2]
    assert first["next_cursor"]
    second = (await client.get(f"/api/v1/org/classes?limit=2&cursor={first['next_cursor']}",
                               headers=teacher)).json()
    assert [c["id"] for c in second["items"]] == [ids[0]]
    assert second["next_cursor"] is None
    resp = await client.get("/api/v1/org/classes?cursor=garbage", headers=teacher)
    assert resp.status_code == 400


# --- months -------------------------------------------------------------------------------

async def test_months(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher)
    m = await create_month(client, teacher, c["id"])
    assert m["effective_fee_cents"] == 200000 and m["fee_cents"] is None and m["status"] == "open"

    discounted = await create_month(client, teacher, c["id"], "2026-12-01", fee_cents=150000, status="upcoming")
    assert discounted["effective_fee_cents"] == 150000

    resp = await client.post(f"/api/v1/org/classes/{c['id']}/months", json={"month_start": "2026-11-01"},
                             headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "MONTH_EXISTS"
    resp = await client.post(f"/api/v1/org/classes/{c['id']}/months", json={"month_start": "2026-11-15"},
                             headers=teacher)
    assert resp.status_code == 422

    closed = await client.patch(f"/api/v1/org/months/{m['id']}", json={"status": "closed"}, headers=teacher)
    assert closed.json()["status"] == "closed"
    listed = (await client.get(f"/api/v1/org/classes/{c['id']}/months", headers=teacher)).json()
    assert [x["month_start"] for x in listed] == ["2026-11-01", "2026-12-01"]


async def test_only_monthly_classes_have_months(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher, pricing_model="free", monthly_fee_cents=None)
    resp = await client.post(f"/api/v1/org/classes/{c['id']}/months", json={"month_start": "2026-11-01"},
                             headers=teacher)
    assert resp.status_code == 400 and error_code(resp) == "NOT_MONTHLY"


async def test_month_with_lessons_cannot_be_deleted(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher)
    m = await create_month(client, teacher, c["id"])
    lesson = (await client.post(f"/api/v1/org/classes/{c['id']}/lessons", headers=teacher, json={
        "class_month_id": m["id"], "title": "Tute 1", "lesson_type": "document"})).json()
    resp = await client.delete(f"/api/v1/org/months/{m['id']}", headers=teacher)
    assert resp.status_code == 409 and error_code(resp) == "MONTH_HAS_LESSONS"
    assert (await client.delete(f"/api/v1/org/lessons/{lesson['id']}", headers=teacher)).status_code == 204
    assert (await client.delete(f"/api/v1/org/months/{m['id']}", headers=teacher)).status_code == 204


# --- lessons ------------------------------------------------------------------------------

async def test_lesson_rules(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher)
    other = await create_class(client, teacher, title="Other")
    m = await create_month(client, teacher, c["id"])
    foreign_month = await create_month(client, teacher, other["id"])
    url = f"/api/v1/org/classes/{c['id']}/lessons"

    cases = [
        ({"title": "x", "lesson_type": "recorded"}, 400, "MONTH_REQUIRED"),
        ({"title": "x", "lesson_type": "recorded", "class_month_id": foreign_month["id"]}, 400, "MONTH_INVALID"),
        ({"title": "x", "lesson_type": "live", "class_month_id": m["id"]}, 400, "SCHEDULE_REQUIRED"),
        ({"title": "x", "lesson_type": "recorded", "class_month_id": m["id"],
          "zoom_join_url": "https://zoom.us/j/1"}, 400, "ZOOM_NOT_ALLOWED"),
        ({"title": "x", "lesson_type": "live", "class_month_id": m["id"], "scheduled_at": "2026-11-03T13:30:00Z",
          "zoom_join_url": "http://zoom.us/j/1"}, 422, "VALIDATION_ERROR"),
        ({"title": "x", "lesson_type": "live", "class_month_id": m["id"],
          "scheduled_at": "2026-11-03T13:30:00"}, 422, "VALIDATION_ERROR"),   # no timezone
    ]
    for body, status, code in cases:
        resp = await client.post(url, json=body, headers=teacher)
        assert (resp.status_code, error_code(resp)) == (status, code), body


async def test_lesson_lifecycle(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher)
    nov = await create_month(client, teacher, c["id"])
    dec = await create_month(client, teacher, c["id"], "2026-12-01")
    url = f"/api/v1/org/classes/{c['id']}/lessons"

    live = (await client.post(url, headers=teacher, json={
        "class_month_id": nov["id"], "title": "Mechanics live", "lesson_type": "live",
        "scheduled_at": "2026-11-03T13:30:00+05:30", "duration_minutes": 120,
        "zoom_join_url": "https://zoom.us/j/123"})).json()
    assert live["scheduled_at"].startswith("2026-11-03T08:00:00")
    await client.post(url, headers=teacher, json={
        "class_month_id": dec["id"], "title": "Tute", "lesson_type": "document"})

    in_nov = (await client.get(f"{url}?month_id={nov['id']}", headers=teacher)).json()
    assert [x["id"] for x in in_nov] == [live["id"]]
    assert len((await client.get(url, headers=teacher)).json()) == 2

    # Turning a live lesson into a recording while it still has a Zoom link is refused.
    lesson_url = f"/api/v1/org/lessons/{live['id']}"
    resp = await client.patch(lesson_url, json={"lesson_type": "recorded"}, headers=teacher)
    assert resp.status_code == 400 and error_code(resp) == "ZOOM_NOT_ALLOWED"
    resp = await client.patch(lesson_url, json={"lesson_type": "recorded", "zoom_join_url": None,
                                                "class_month_id": dec["id"], "is_published": True},
                              headers=teacher)
    assert resp.status_code == 200
    assert resp.json()["class_month_id"] == dec["id"] and resp.json()["is_published"] is True

    assert (await client.delete(lesson_url, headers=teacher)).status_code == 204
    assert (await client.patch(lesson_url, json={"title": "y"}, headers=teacher)).status_code == 404


async def test_one_time_class_lessons_have_no_month(client: AsyncClient, teacher: Headers) -> None:
    c = await create_class(client, teacher, pricing_model="one_time", monthly_fee_cents=None,
                           one_time_price_cents=900000)
    resp = await client.post(f"/api/v1/org/classes/{c['id']}/lessons", headers=teacher,
                             json={"title": "Paper class", "lesson_type": "recorded"})
    assert resp.status_code == 201 and resp.json()["class_month_id"] is None


# --- isolation (CLAUDE.md section 5, rule 8) ----------------------------------------------

async def test_catalog_tables_isolated(client: AsyncClient, sms: FakeSms, seed: Seed, teacher: Headers) -> None:
    in_b = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    for h in (teacher, in_b):
        c = await create_class(client, h)
        m = await create_month(client, h, c["id"])
        await client.post(f"/api/v1/org/classes/{c['id']}/lessons", headers=h,
                          json={"class_month_id": m["id"], "title": "Tute", "lesson_type": "document"})

    ids = [seed.a.id, seed.b.id]
    async with tenant_transaction(seed.a.id) as session:
        for table in ("class_months", "lessons", "audit_logs"):
            seen = set((await session.execute(
                text(f"SELECT DISTINCT tenant_id FROM {table} WHERE tenant_id = ANY(:ids)"), {"ids": ids}
            )).scalars())
            assert seen == {seed.a.id}, table
        touched = await session.execute(
            text("UPDATE lessons SET title = 'hacked' WHERE tenant_id = :b"), {"b": seed.b.id})
    assert touched.rowcount == 0  # type: ignore[attr-defined]
