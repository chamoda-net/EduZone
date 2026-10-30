"""Phase 3: path tenancy for the console (/teach/<tenant>), the student area across tenants
(/learn), and the user-scoped RLS reads behind it (CLAUDE.md section 5, rule 4)."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.core.db import AdminSession, AppSession
from app.core.tenancy import tenant_transaction, user_transaction
from tests.conftest import AddMember, FakeSms, Seed
from tests.helpers import Phones, auth_headers, error_code, login
from tests.test_checkout import notify, payment_key
from tests.test_learning import monthly_class

Headers = dict[str, str]
MAIN = SimpleNamespace(host=get_settings().base_domain)  # the main site: no tenant in the host


def on_main(h: Headers) -> Headers:
    return {"host": MAIN.host, "authorization": h["authorization"]}


async def main_login(client: AsyncClient, sms: FakeSms, phone: str) -> Headers:
    tokens = await login(client, sms, MAIN, phone)  # type: ignore[arg-type]
    return {"host": MAIN.host, "authorization": f"Bearer {tokens['access_token']}"}


async def user_id_of(phone: str) -> UUID:
    async with AdminSession() as s:
        return (await s.execute(text("SELECT id FROM users WHERE phone = :p"), {"p": phone})).scalar_one()


# --- /teach/<tenant>: the tenant comes from the path, plus a membership check ----------------

async def test_teach_routes_take_the_tenant_from_the_path(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    teacher = on_main(await auth_headers(client, sms, seed.a, seed.a.teacher_phone))
    assert (await client.get(f"/api/v1/teach/{seed.a.slug}/classes", headers=teacher)).status_code == 200

    other = await client.get(f"/api/v1/teach/{seed.b.slug}/classes", headers=teacher)
    assert other.status_code == 403 and error_code(other) == "ACCESS_DENIED"
    for slug in ("no-such-org", seed.suspended.slug, "Bad_Slug!"):
        assert (await client.get(f"/api/v1/teach/{slug}/classes", headers=teacher)).status_code == 404

    # The path wins over the host: a write via /teach/<a> on B's host lands in A.
    on_b = {"host": seed.b.host, "authorization": teacher["authorization"]}
    made = await client.post(f"/api/v1/teach/{seed.a.slug}/classes", headers=on_b,
                             json={"title": "Path Class", "pricing_model": "free"})
    assert made.status_code == 201
    async with tenant_transaction(seed.a.id) as s:
        assert (await s.execute(text("SELECT count(*) FROM classes WHERE id = :c"),
                                {"c": made.json()["id"]})).scalar_one() == 1


async def test_me_on_the_main_host_lists_workspaces(client: AsyncClient, seed: Seed, sms: FakeSms,
                                                     phones: Phones) -> None:
    teacher = await main_login(client, sms, seed.a.teacher_phone)
    me = (await client.get("/api/v1/auth/me", headers=teacher)).json()
    assert me["member_id"] is None and me["role"] is None
    assert me["workspaces"] == [{"slug": seed.a.slug, "name": seed.a.name, "role": "teacher"}]
    student = await main_login(client, sms, phones())
    assert (await client.get("/api/v1/auth/me", headers=student)).json()["workspaces"] == []


# --- /learn: one account, every teacher ---------------------------------------------------

async def _live_soon(client: AsyncClient, teacher: Headers, class_id: str, month_id: str) -> dict[str, Any]:
    at = (datetime.now(UTC) + timedelta(days=2)).isoformat()
    return (await client.post(f"/api/v1/org/classes/{class_id}/lessons", headers=teacher, json={
        "class_month_id": month_id, "title": "Live soon", "lesson_type": "live", "scheduled_at": at,
        "zoom_join_url": "https://zoom.us/j/222", "is_published": True})).json()


async def test_student_area_spans_tenants(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones,
                                          members: AddMember) -> None:
    teacher_a = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    teacher_b = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    ka = await monthly_class(client, teacher_a)
    kb = await monthly_class(client, teacher_b, title="O/L Maths")
    soon = await _live_soon(client, teacher_a, ka["class"]["id"], ka["months"]["open"]["id"])

    student = await main_login(client, sms, phones())
    for k, t in ((ka, seed.a), (kb, seed.b)):
        joined = await client.post(f"/api/v1/learn/classes/{k['class']['id']}/enroll", headers=student)
        assert joined.status_code == 200 and joined.json()["enrolled"] is True
        assert joined.json()["class"]["org"] == {"slug": t.slug, "name": t.name}

    mine = (await client.get("/api/v1/learn/classes", headers=student)).json()
    assert {c["class"]["org"]["slug"] for c in mine} == {seed.a.slug, seed.b.slug}

    today = (await client.get("/api/v1/learn/today", headers=student)).json()
    assert today["classes"] == 2 and today["pending_requests"] == 0
    assert {m["month_id"] for m in today["to_pay"]} == {ka["months"]["open"]["id"], kb["months"]["open"]["id"]}
    schedule = (await client.get("/api/v1/learn/schedule", headers=student)).json()
    assert [(s["lesson_id"], s["unlocked"]) for s in schedule if s["lesson_id"] == soon["id"]] == [(soon["id"], False)]

    # Pay for A's open month from the main site.
    out = await client.post("/api/v1/learn/checkout", headers=student,
                            json={"class_id": ka["class"]["id"], "class_month_id": ka["months"]["open"]["id"]})
    assert out.status_code == 201, out.text
    order_id = out.json()["order"]["id"]
    assert out.json()["order"]["item"]["class_slug"] == ka["class"]["slug"]
    assert (await client.get("/api/v1/learn/payments", headers=student)).json() == []   # pending isn't listed
    assert (await notify(client, payment_key(out.json()))).status_code == 200

    order = (await client.get(f"/api/v1/learn/orders/{order_id}", headers=student)).json()
    assert order["status"] == "paid" and order["org"]["slug"] == seed.a.slug
    paid = (await client.get("/api/v1/learn/payments", headers=student)).json()
    assert [(p["id"], p["org"]["slug"]) for p in paid] == [(order_id, seed.a.slug)]

    lesson = (await client.get(f"/api/v1/learn/lessons/{soon['id']}", headers=student)).json()
    assert lesson["unlocked"] is True and lesson["zoom_join_url"] == "https://zoom.us/j/222"
    assert lesson["org"]["slug"] == seed.a.slug
    today = (await client.get("/api/v1/learn/today", headers=student)).json()
    assert [m["month_id"] for m in today["to_pay"]] == [kb["months"]["open"]["id"]]

    # A past month in B: ask the teacher; it shows in requests and on Today.
    asked = await client.post(f"/api/v1/learn/months/{kb['months']['closed']['id']}/late-request",
                              headers=student, json={"note": "Joined late"})
    assert asked.status_code == 201
    requests = (await client.get("/api/v1/learn/requests", headers=student)).json()
    assert [(r["status"], r["org"]["slug"], r["class_title"]) for r in requests] == [("pending", seed.b.slug, "O/L Maths")]
    assert (await client.get("/api/v1/learn/today", headers=student)).json()["pending_requests"] == 1

    # Someone else sees none of it.
    stranger = await main_login(client, sms, await members(seed.a, "student"))
    assert (await client.get(f"/api/v1/learn/orders/{order_id}", headers=stranger)).status_code == 404
    assert (await client.get("/api/v1/learn/payments", headers=stranger)).json() == []
    assert (await client.get("/api/v1/learn/requests", headers=stranger)).json() == []
    locked = (await client.get(f"/api/v1/learn/lessons/{soon['id']}", headers=stranger)).json()
    assert locked["unlocked"] is False and locked["zoom_join_url"] is None


async def test_learn_routes_404_for_unknown_ids(client: AsyncClient, sms: FakeSms, phones: Phones) -> None:
    student = await main_login(client, sms, phones())
    missing = "00000000-0000-0000-0000-000000000000"
    for path in (f"classes/{missing}", f"lessons/{missing}", f"orders/{missing}"):
        assert (await client.get(f"/api/v1/learn/{path}", headers=student)).status_code == 404
    assert (await client.get("/api/v1/learn/today")).status_code == 401


# --- user-scoped RLS (migration 0006) -------------------------------------------------------

async def _enrol(tenant_id: UUID, class_id: UUID, user_id: UUID) -> None:
    async with tenant_transaction(tenant_id) as s:
        member = (await s.execute(text("SELECT id FROM tenant_members WHERE user_id = :u"), {"u": user_id})).scalar_one()
        await s.execute(text("""
            INSERT INTO class_enrollments (tenant_id, class_id, student_member_id)
            VALUES (current_tenant_id(), :c, :m)
        """), {"c": class_id, "m": member})


async def test_user_scope_sees_only_own_rows_across_tenants(seed: Seed, members: AddMember) -> None:
    phone_a = await members(seed.a, "student")
    phone_b = await members(seed.a, "student")
    user_a, user_b = await user_id_of(phone_a), await user_id_of(phone_b)
    async with AdminSession() as s, s.begin():   # user A is a member of both tenants
        await s.execute(text("INSERT INTO tenant_members (tenant_id, user_id, role) VALUES (:t, :u, 'student')"),
                        {"t": seed.b.id, "u": user_a})
    await _enrol(seed.a.id, seed.a.class_id, user_a)
    await _enrol(seed.b.id, seed.b.class_id, user_a)
    await _enrol(seed.a.id, seed.a.class_id, user_b)

    async with user_transaction(user_a) as s:
        members_seen = (await s.execute(text("SELECT tenant_id, user_id FROM tenant_members"))).all()
        tenants_seen = set((await s.execute(text("SELECT id FROM tenants"))).scalars())
        enrolments = (await s.execute(text("SELECT tenant_id FROM class_enrollments"))).scalars().all()
        classes = (await s.execute(text("SELECT count(*) FROM classes"))).scalar_one()
    assert {r.user_id for r in members_seen} == {user_a} and len(members_seen) == 2
    assert tenants_seen == {seed.a.id, seed.b.id}
    assert sorted(map(str, enrolments)) == sorted(map(str, (seed.a.id, seed.b.id)))
    assert classes == 0                          # only student-owned tables are user-readable

    async with user_transaction(user_b) as s:
        assert (await s.execute(text("SELECT count(*) FROM class_enrollments"))).scalar_one() == 1
        assert set((await s.execute(text("SELECT id FROM tenants"))).scalars()) == {seed.a.id}

    # No scope at all: nothing. Writes through the user scope are refused by the tenant policy.
    async with AppSession() as s:
        assert (await s.execute(text("SELECT count(*) FROM tenant_members"))).scalar_one() == 0
    with pytest.raises(DBAPIError):
        async with user_transaction(user_a) as s:
            await s.execute(text("""
                INSERT INTO class_enrollments (tenant_id, class_id, student_member_id)
                SELECT tenant_id, :c, id FROM tenant_members WHERE tenant_id = :t
            """), {"c": seed.b.class_id, "t": seed.b.id})


async def test_staff_lookup_ignores_rls(seed: Seed) -> None:
    """user_is_staff_anywhere() must see members without a tenant set (owned by eduzone_admin)."""
    async with AdminSession() as s:
        teacher = (await s.execute(text("SELECT id FROM users WHERE phone = :p"),
                                   {"p": seed.a.teacher_phone})).scalar_one()
    async with AppSession() as s:
        assert (await s.execute(text("SELECT user_is_staff_anywhere(:u)"), {"u": teacher})).scalar_one() is True
