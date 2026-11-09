"""Courses, step C2 (docs/COURSES.md): courses on the public marketplace. The catalogue and its filters, category
pages, the landing page, instructor pages, free previews, and the narrow read path (public course views)."""

from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AdminSession, AppSession
from tests.conftest import Seed
from tests.test_courses import (  # noqa: F401  (fixtures)
    O,
    P,
    category_id,
    curriculum,
    landing,
    new_course,
    ready_video,
    teacher,
)
from tests.test_market import published
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
M = "/api/v1/market"


async def live_course(client: AsyncClient, seed: Seed, h: Headers, ph: Headers, title: str) -> dict[str, Any]:  # noqa: F811
    """A course built, submitted and approved: on the marketplace. Its first lecture is a free preview and it has
    a promo video."""
    course = await new_course(client, h, title)
    await landing(client, h, course["id"])
    detail = await curriculum(client, h, seed.a, course["id"])
    first = detail["sections"][0]["lectures"][0]
    await client.patch(f"{O}/lectures/{first['id']}", headers=h, json={"is_free_preview": True})
    await client.patch(f"{O}/courses/{course['id']}", headers=h,
                       json={"promo_media_id": await ready_video(seed.a, 90)})
    assert (await client.post(f"{O}/courses/{course['id']}/submit", headers=h)).status_code == 200
    live = await client.post(f"{P}/courses/{course['id']}/decision", headers=ph, json={"decision": "approve"})
    assert live.status_code == 200, live.text
    return live.json()


@pytest.fixture
async def ccna(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers) -> dict[str, Any]:  # noqa: F811
    return await live_course(client, seed, teacher, ph, f"CCNA Complete {uuid4().hex[:6]}")


def slugs(page: Any) -> set[str]:
    return {c["slug"] for c in page["items"]}


async def test_catalogue_and_filters(client: AsyncClient, ccna: dict[str, Any]) -> None:
    slug = ccna["slug"]
    page = (await client.get(f"{M}/courses", params={"limit": 60})).json()
    card = next(c for c in page["items"] if c["slug"] == slug)
    assert card["path"] == f"/course/{slug}" and card["category_slug"] == "it-networking"
    assert (card["lecture_count"], card["total_video_seconds"], card["one_time_price_cents"]) == (5, 32 * 60, 300000)
    assert card["teacher_name"] == "Teacher A" and card["students"] == 0 and card["rating_avg"] is None

    async def found(**params: Any) -> bool:
        return slug in slugs((await client.get(f"{M}/courses", params={**params, "limit": 60})).json())

    assert await found(q="ccna") and await found(q="subnetting")      # title and description
    assert not await found(q="zzzz-nothing")
    assert await found(category="it-networking") and not await found(category="business")
    assert await found(level="beginner") and not await found(level="advanced")
    assert await found(language="en") and not await found(language="si")
    assert await found(price="paid") and not await found(price="free")
    assert await found(max_price=300000) and not await found(max_price=299999)
    assert await found(length="short") and not await found(length="long")
    assert not await found(rating=4)                                     # no ratings yet (step C4)
    for sort in ("popular", "rating", "newest", "price_low", "price_high"):
        assert (await client.get(f"{M}/courses", params={"sort": sort})).status_code == 200
    assert (await client.get(f"{M}/courses", params={"sort": "cheap"})).status_code == 422


async def test_landing_page_shows_only_public_fields(client: AsyncClient, ccna: dict[str, Any]) -> None:
    r = await client.get(f"{M}/course/{ccna['slug']}")
    assert r.status_code == 200
    d = r.json()
    assert d["course"]["title"] == ccna["title"] and d["has_promo"] is True
    assert len(d["learning_objectives"]) == 4 and d["requirements"] == ["No prior experience needed"]
    assert [len(s["lectures"]) for s in d["sections"]] == [2, 3]
    first = d["sections"][0]["lectures"][0]
    assert first["is_free_preview"] and first["can_preview"] and first["video_seconds"] == 8 * 60
    article = d["sections"][1]["lectures"][-1]
    assert article["lesson_type"] == "article" and not article["can_preview"]
    assert d["instructor"]["slug"] and d["instructor"]["course_count"] >= 1
    # Never the article text, lecture descriptions, files or internal ids of the organization.
    body = r.text
    assert "OSPF\\nAreas" not in body and "article_body" not in body and "media_asset" not in body
    assert "tenant_id" not in body and "promo_media_id" not in body

    # Hidden lectures leave the outline.
    assert (await client.get(f"{M}/course/no-such-course")).status_code == 404


async def test_previews(client: AsyncClient, ccna: dict[str, Any]) -> None:
    d = (await client.get(f"{M}/course/{ccna['slug']}")).json()
    promo = await client.post(f"{M}/course/{ccna['slug']}/preview", json={})
    assert promo.status_code == 200, promo.text
    assert promo.json()["playback"] in ("hls", "embed") and promo.json()["url"]
    first = d["sections"][0]["lectures"][0]
    lecture = await client.post(f"{M}/course/{ccna['slug']}/preview", json={"lecture_id": first["id"]})
    assert lecture.status_code == 200 and lecture.json()["title"] == first["title"]
    locked = d["sections"][0]["lectures"][1]
    assert (await client.post(f"{M}/course/{ccna['slug']}/preview",
                              json={"lecture_id": locked["id"]})).status_code == 404
    assert (await client.post(f"{M}/course/{ccna['slug']}/preview",
                              json={"lecture_id": str(uuid4())})).status_code == 404


async def test_what_hides_a_course(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers,  # noqa: F811
                                   ccna: dict[str, Any]) -> None:
    slug = ccna["slug"]

    async def public() -> bool:
        return (await client.get(f"{M}/course/{slug}")).status_code == 200

    # A draft course of the same teacher never shows.
    draft = await new_course(client, teacher, "Draft only")
    assert (await client.get(f"{M}/course/{draft['slug']}")).status_code == 404

    # Unpublished by the instructor.
    await client.post(f"{O}/courses/{ccna['id']}/unpublish", headers=teacher)
    assert not await public()
    await client.post(f"{O}/courses/{ccna['id']}/submit", headers=teacher)
    assert await public()

    # The organization unlisted, or its category hidden.
    await client.patch(f"{P}/tenants/{seed.a.id}", headers=ph, json={"is_listed": False})
    try:
        assert not await public()
    finally:
        await client.patch(f"{P}/tenants/{seed.a.id}", headers=ph, json={"is_listed": True})
    cat = await category_id()
    await client.patch(f"{P}/course-categories/{cat}", headers=ph, json={"is_active": False})
    try:
        assert not await public()
        assert "it-networking" not in {c["slug"] for c in (await client.get(f"{M}/courses/categories")).json()}
    finally:
        await client.patch(f"{P}/course-categories/{cat}", headers=ph, json={"is_active": True})
    assert await public()


async def test_categories_home_instructor_sitemap(client: AsyncClient, seed: Seed, teacher: Headers,
                                                  ph: Headers, ccna: dict[str, Any]) -> None:  # noqa: F811
    cats = (await client.get(f"{M}/courses/categories")).json()
    it = next(c for c in cats if c["slug"] == "it-networking")
    assert it["parent_id"] is None and it["course_count"] >= 1
    page = (await client.get(f"{M}/courses/categories/it-networking")).json()
    assert page["category"]["slug"] == "it-networking" and page["parent"] is None
    assert (await client.get(f"{M}/courses/categories/no-such")).status_code == 404

    home = (await client.get(f"{M}/courses/home")).json()
    assert home["total"] >= 1 and ccna["slug"] in {c["slug"] for c in home["popular"]}
    assert ccna["slug"] in {c["slug"] for c in home["newest"]}
    assert ccna["slug"] not in {c["slug"] for c in home["top_rated"]}      # no ratings yet
    assert any(c["slug"] == "it-networking" for c in home["categories"])

    # One page per person: their courses and their tuition classes.
    await published(client, teacher)
    d = (await client.get(f"{M}/course/{ccna['slug']}")).json()
    inst = (await client.get(f"{M}/instructors/{d['instructor']['slug']}")).json()
    assert ccna["slug"] in {c["slug"] for c in inst["courses"]}
    assert inst["classes"] and inst["instructor"]["class_count"] >= 1
    assert (await client.get(f"{M}/instructors/nobody-here")).status_code == 404

    sitemap = (await client.get(f"{M}/sitemap")).json()
    assert f"/course/{ccna['slug']}" in sitemap["courses"]
    assert "/courses/it-networking" in sitemap["course_categories"]
    assert f"/instructor/{d['instructor']['slug']}" in sitemap["instructors"]


async def test_public_course_views_are_narrow() -> None:
    async with AppSession() as s:
        lectures = set((await s.execute(text("SELECT * FROM public_course_lectures LIMIT 0"))).keys())
        courses = set((await s.execute(text("SELECT * FROM public_courses LIMIT 0"))).keys())
        # The app role still sees no course data outside the views.
        assert (await s.execute(text("SELECT count(*) FROM course_sections"))).scalar_one() == 0
    assert lectures == {"id", "course_id", "section_id", "title", "lesson_type", "sort_order", "is_free_preview",
                        "video_seconds"}
    assert not courses & {"promo_media_id", "review_note", "teacher_member_id", "welcome_message",
                          "completion_message", "max_video_views", "status"}
    async with AdminSession() as s:
        owner = (await s.execute(text(
            "SELECT viewowner FROM pg_views WHERE viewname = 'public_course_lectures'"))).scalar_one()
    assert owner == "eduzone_admin"
