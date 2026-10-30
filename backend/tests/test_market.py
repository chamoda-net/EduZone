"""Phase 4: the public marketplace read path (views owned by eduzone_admin), search, pages, listing,
and teacher profiles."""

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import AdminSession, AppSession
from tests.conftest import FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_learning import monthly_class

Headers = dict[str, str]


async def physics_id() -> str:
    async with AdminSession() as s:
        return str((await s.execute(text("SELECT id FROM subjects WHERE slug = 'physics'"))).scalar_one())


async def published(client: AsyncClient, teacher: Headers, **overrides: Any) -> dict[str, Any]:
    """A published monthly class with the physics subject (monthly_class publishes it)."""
    k = await monthly_class(client, teacher, subject_id=await physics_id(), **overrides)
    assert k["class"]["subject"] == "Physics"
    return k


async def profile_slug(teacher_phone: str) -> str:
    async with AdminSession() as s:
        return (await s.execute(text("""
            SELECT tp.slug FROM teacher_profiles tp JOIN users u ON u.id = tp.user_id WHERE u.phone = :p
        """), {"p": teacher_phone})).scalar_one()


async def test_publishing_lists_the_class_under_the_teacher(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    teacher = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    k = await published(client, teacher, title="Mechanics Masterclass")
    slug = await profile_slug(seed.a.teacher_phone)               # created on publish

    found = (await client.get("/api/v1/market/classes?q=mechan&subject=physics")).json()
    card = next(c for c in found["items"] if c["id"] == k["class"]["id"])
    assert card["path"] == f"/physics/{slug}/{k['class']['slug']}"
    assert card["org_slug"] == seed.a.slug and card["has_live"] is True
    assert card["open_month_start"] == "2026-11-01"

    detail = (await client.get(f"/api/v1/market/classes{card['path']}")).json()
    assert detail["class"]["id"] == k["class"]["id"] and detail["teacher"]["slug"] == slug
    assert [m["status"] for m in detail["months"]] == ["closed", "open", "upcoming"]
    assert all("zoom_join_url" not in lesson and "description" not in lesson for lesson in detail["lessons"])
    assert "Draft notes" not in [lesson["title"] for lesson in detail["lessons"]]   # unpublished lessons stay out

    page = (await client.get(f"/api/v1/market/teachers/{slug}?subject=physics")).json()
    assert page["subject"] == {"slug": "physics", "name": "Physics"}
    assert k["class"]["id"] in [c["id"] for c in page["classes"]]
    assert (await client.get(f"/api/v1/market/teachers/{slug}?subject=chemistry")).status_code == 404
    subject = (await client.get("/api/v1/market/subjects/physics")).json()
    assert slug in [t["slug"] for t in subject["teachers"]]
    assert (await client.get(f"/api/v1/market/classes/by-id/{k['class']['id']}")).json()["path"] == card["path"]
    assert card["path"] in (await client.get("/api/v1/market/sitemap")).json()["classes"]


async def test_only_public_classes_are_listed(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    teacher_a = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    k = await published(client, teacher_a, title="Listed Physics")
    draft = (await client.post("/api/v1/org/classes", headers=teacher_a, json={
        "title": "Draft Physics", "pricing_model": "free", "subject_id": await physics_id()})).json()
    no_subject = await monthly_class(client, teacher_a, title="No Subject Class")

    ids = {c["id"] for c in (await client.get("/api/v1/market/classes?limit=60&org=" + seed.a.slug)).json()["items"]}
    assert k["class"]["id"] in ids and draft["id"] not in ids and no_subject["class"]["id"] not in ids

    # Unlisting the organization (or suspending it) takes its classes off the marketplace.
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE tenants SET is_listed = false WHERE id = :t"), {"t": seed.a.id})
    gone = (await client.get(f"/api/v1/market/classes/by-id/{k['class']['id']}"))
    assert gone.status_code == 404


async def test_public_views_expose_public_fields_only() -> None:
    """The app role reads the views across tenants, but tenant tables stay closed to it."""
    async with AppSession() as s:
        columns = set((await s.execute(text("SELECT * FROM public_classes LIMIT 0"))).keys())
        assert (await s.execute(text("SELECT count(*) FROM classes"))).scalar_one() == 0
        assert (await s.execute(text("SELECT count(*) FROM lessons"))).scalar_one() == 0
        lesson_columns = set((await s.execute(text("SELECT * FROM public_lessons LIMIT 0"))).keys())
    assert not {"zoom_join_url", "commission_bps", "bunny_library_id", "teacher_member_id"} & columns
    assert "zoom_join_url" not in lesson_columns and "description" not in lesson_columns


async def test_teacher_edits_their_profile(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    teacher = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    await published(client, teacher)
    mine = (await client.get("/api/v1/me/teacher-profile", headers=teacher)).json()
    new_slug = f"{mine['slug'][:30]}-x"
    saved = await client.put("/api/v1/me/teacher-profile", headers=teacher, json={
        "slug": new_slug, "display_name": "  Mr  Kasun ", "headline": "B.Sc Physics · 12 years",
        "bio": "Physics for A/L.", "highlights": ["120 A passes in 2025", "  ", "Author of 3 books"]})
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["display_name"] == "Mr Kasun" and body["highlights"] == ["120 A passes in 2025", "Author of 3 books"]
    assert body["public_paths"] == [f"/physics/{new_slug}"]
    page = (await client.get(f"/api/v1/market/teachers/{new_slug}")).json()
    assert page["teacher"]["headline"] == "B.Sc Physics · 12 years"

    bad = await client.put("/api/v1/me/teacher-profile", headers=teacher, json={"slug": "No Spaces", "display_name": "X"})
    assert bad.status_code == 422


async def test_profile_slugs_are_unique_and_students_have_none(client: AsyncClient, seed: Seed, sms: FakeSms,
                                                               phones: Any) -> None:
    teacher_a = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    teacher_b = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    taken = (await client.get("/api/v1/me/teacher-profile", headers=teacher_a)).json()["slug"]
    clash = await client.put("/api/v1/me/teacher-profile", headers=teacher_b, json={"slug": taken, "display_name": "B"})
    assert clash.status_code == 409 and error_code(clash) == "PROFILE_SLUG_TAKEN"
    student = await auth_headers(client, sms, seed.a, phones())
    assert (await client.get("/api/v1/me/teacher-profile", headers=student)).status_code == 403


async def test_subject_slugs_never_shadow_app_routes() -> None:
    async with AdminSession() as s:
        assert (await s.execute(text("SELECT is_reserved_slug('learn') AND NOT is_reserved_slug('physics')"))).scalar_one()
    with pytest.raises(IntegrityError, match="check"):
        async with AdminSession() as s, s.begin():
            await s.execute(text("INSERT INTO subjects (slug, name) VALUES ('login', 'Login')"))


async def test_home_and_search_filters(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    teacher = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    k = await published(client, teacher, title="Optics Revision", exam="al", batch_year=2027, medium="si")
    home = (await client.get("/api/v1/market/home")).json()
    assert home["classes"] >= 1 and any(s["slug"] == "physics" and s["class_count"] >= 1 for s in home["subjects"])

    def has(resp: Any) -> bool:
        return k["class"]["id"] in [c["id"] for c in resp.json()["items"]]

    assert has(await client.get("/api/v1/market/classes?q=optics&exam=al&year=2027&medium=si&format=live"))
    assert not has(await client.get("/api/v1/market/classes?q=optics&exam=ol"))
    assert not has(await client.get("/api/v1/market/classes?q=optics&format=recorded"))
    assert not has(await client.get("/api/v1/market/classes?q=optics&max_fee=100"))
    assert has(await client.get("/api/v1/market/classes?q=optics&max_fee=200000&sort=price"))
    assert (await client.get("/api/v1/market/classes?cursor=!!!")).status_code == 400
