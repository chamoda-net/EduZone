"""Courses, step C1 (docs/COURSES.md): the course builder, publish checks, the first-publish review by EduZone
staff, course categories, and keeping courses out of the tuition screens and checkout until step C3."""

from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AdminSession, AppSession
from app.core.tenancy import tenant_transaction
from app.modules.onboarding.schemas import ApplicationFields
from tests.conftest import AddMember, FakeSms, Seed, SeededTenant
from tests.helpers import auth_headers, error_code
from tests.test_learn import main_login
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
O = "/api/v1/org"
P = "/api/v1/platform"

LONG_DESCRIPTION = " ".join(["Subnetting, routing and switching explained step by step."] * 15)  # 120 words


@pytest.fixture
async def teacher(client: AsyncClient, sms: FakeSms, seed: Seed) -> Headers:
    """Tenant A's teacher, with a public profile (photo and bio) as publishing requires."""
    async with AdminSession() as s, s.begin():
        await s.execute(text("""
            INSERT INTO teacher_profiles (user_id, slug, display_name, bio, photo_url)
            SELECT u.id, 'ccna-' || substr(md5(random()::text), 1, 8), 'Teacher A', 'Cisco instructor, 12 years.',
                   'https://example.com/photo.jpg'
            FROM users u WHERE u.phone = :p
            ON CONFLICT (user_id) DO UPDATE SET bio = EXCLUDED.bio, photo_url = EXCLUDED.photo_url
        """), {"p": seed.a.teacher_phone})
    return await auth_headers(client, sms, seed.a, seed.a.teacher_phone)


@pytest.fixture
async def new_categories() -> AsyncIterator[list[str]]:
    slugs: list[str] = []
    yield slugs
    if slugs:
        async with AdminSession() as s, s.begin():
            await s.execute(text("DELETE FROM course_categories WHERE parent_id IN "
                                 "(SELECT id FROM course_categories WHERE slug = ANY(:s))"), {"s": slugs})
            await s.execute(text("DELETE FROM course_categories WHERE slug = ANY(:s)"), {"s": slugs})


async def category_id(slug: str = "it-networking") -> int:
    async with AppSession() as s:
        return int((await s.execute(text("SELECT id FROM course_categories WHERE slug = :s"), {"s": slug})).scalar_one())


async def ready_video(tenant: SeededTenant, seconds: int) -> str:
    """A processed video in the tenant's media library (no Bunny needed)."""
    async with tenant_transaction(tenant.id) as s:
        return str((await s.execute(text("""
            INSERT INTO media_assets (tenant_id, uploaded_by, kind, provider, external_id, original_filename,
                                      mime_type, size_bytes, duration_seconds, status)
            VALUES (:t, :m, 'video', 'bunny_stream', :x, 'lecture.mp4', 'video/mp4', 1000, :sec, 'ready')
            RETURNING id
        """), {"t": tenant.id, "m": tenant.member_id, "x": f"test-{uuid4().hex}", "sec": seconds})).scalar_one())


async def landing(client: AsyncClient, h: Headers, course_id: str) -> Any:
    r = await client.patch(f"{O}/courses/{course_id}", headers=h, json={
        "subtitle": "Pass the CCNA in 8 weeks", "description": LONG_DESCRIPTION, "level": "beginner",
        "medium": "en", "cover_image_url": "https://example.com/cover.jpg", "category_id": await category_id(),
        "learning_objectives": ["Subnet any network", "Configure VLANs", "Set up OSPF", "Secure a switch"],
        "requirements": ["No prior experience needed"], "target_audience": ["New network engineers"],
        "pricing_model": "one_time", "one_time_price_cents": 300000,
        "welcome_message": "Welcome!", "completion_message": "Well done!",
    })
    assert r.status_code == 200, r.text
    return r.json()


async def curriculum(client: AsyncClient, h: Headers, tenant: SeededTenant, course_id: str) -> Any:
    """Two sections, five published lectures: four videos of 8 minutes and an article (32 minutes of video)."""
    detail = (await client.post(f"{O}/courses/{course_id}/sections", headers=h, json={"title": "Basics"})).json()
    detail = (await client.post(f"{O}/courses/{course_id}/sections", headers=h, json={"title": "Routing"})).json()
    first, second = (s["id"] for s in detail["sections"])
    for i in range(4):
        section = first if i < 2 else second
        detail = (await client.post(f"{O}/course-sections/{section}/lectures", headers=h,
                                    json={"title": f"Video {i + 1}", "lesson_type": "recorded"})).json()
        lecture = next(x for s in detail["sections"] for x in s["lectures"] if x["title"] == f"Video {i + 1}")
        attach = await client.post(f"{O}/lessons/{lecture['id']}/resources", headers=h,
                                   json={"media_asset_id": await ready_video(tenant, 8 * 60)})
        assert attach.status_code == 201, attach.text
    r = await client.post(f"{O}/course-sections/{second}/lectures", headers=h, json={
        "title": "Cheat sheet", "lesson_type": "article", "article_body": "# OSPF\nAreas, costs, timers."})
    assert r.status_code == 201, r.text
    return r.json()


async def new_course(client: AsyncClient, h: Headers, title: str = "CCNA Complete") -> Any:
    r = await client.post(f"{O}/courses", headers=h, json={"title": title})
    assert r.status_code == 201, r.text
    return r.json()


# --- building and publishing ------------------------------------------------------------------

async def test_build_submit_review_publish(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers) -> None:  # noqa: F811
    course = await new_course(client, teacher)
    assert course["status"] == "draft" and course["pricing_model"] == "free" and course["needs_review"]
    assert not course["ready_to_submit"]
    early = await client.post(f"{O}/courses/{course['id']}/submit", headers=teacher)
    assert early.status_code == 409 and error_code(early) == "COURSE_NOT_READY"

    await landing(client, teacher, course["id"])
    detail = await curriculum(client, teacher, seed.a, course["id"])
    checks = {c["key"]: c for c in detail["checks"]}
    assert checks["lectures"]["current"] == 5 and checks["video_minutes"]["current"] == 32
    assert checks["description"]["current"] >= 100
    assert detail["ready_to_submit"], [c for c in detail["checks"] if not c["ok"]]

    # First publish goes to EduZone's review; the course is locked meanwhile.
    sent = (await client.post(f"{O}/courses/{course['id']}/submit", headers=teacher)).json()
    assert sent["status"] == "in_review" and sent["submitted_at"]
    locked = await client.patch(f"{O}/courses/{course['id']}", headers=teacher, json={"subtitle": "New"})
    assert locked.status_code == 409 and error_code(locked) == "COURSE_IN_REVIEW"
    assert (await client.post(f"{O}/courses/{course['id']}/sections", headers=teacher,
                              json={"title": "Extra"})).status_code == 409

    queue = (await client.get(f"{P}/courses", headers=ph)).json()
    assert any(r["id"] == course["id"] and r["tenant_name"] == seed.a.name for r in queue)
    review = (await client.get(f"{P}/courses/{course['id']}", headers=ph)).json()
    assert review["tenant_name"] == seed.a.name and len(review["sections"]) == 2

    # Changes requested: a note is required, the course returns to draft with it.
    no_note = await client.post(f"{P}/courses/{course['id']}/decision", headers=ph, json={"decision": "request_changes"})
    assert no_note.status_code == 422 and error_code(no_note) == "NOTE_REQUIRED"
    back = (await client.post(f"{P}/courses/{course['id']}/decision", headers=ph,
                              json={"decision": "request_changes", "note": "Add a promo video please."})).json()
    assert back["status"] == "draft" and back["review_note"] == "Add a promo video please."
    assert (await client.get(f"{O}/courses/{course['id']}", headers=teacher)).json()["review_note"] == back["review_note"]

    # Resubmitted, withdrawn, resubmitted, approved.
    assert (await client.post(f"{O}/courses/{course['id']}/submit", headers=teacher)).json()["status"] == "in_review"
    assert (await client.post(f"{O}/courses/{course['id']}/withdraw", headers=teacher)).json()["status"] == "draft"
    assert (await client.post(f"{O}/courses/{course['id']}/submit", headers=teacher)).json()["review_note"] is None
    live = (await client.post(f"{P}/courses/{course['id']}/decision", headers=ph, json={"decision": "approve"})).json()
    assert live["status"] == "published" and live["first_published_at"] and not live["needs_review"]
    assert (live["lecture_count"], live["total_video_seconds"]) == (5, 32 * 60)

    # Edits now go live without review; unpublishing and publishing again need no review either.
    edited = await client.patch(f"{O}/courses/{course['id']}", headers=teacher, json={"subtitle": "Updated"})
    assert edited.status_code == 200 and edited.json()["status"] == "published"
    slug = await client.patch(f"{O}/courses/{course['id']}", headers=teacher, json={"slug": "new-address"})
    assert slug.status_code == 409 and error_code(slug) == "SLUG_LOCKED"
    assert (await client.post(f"{O}/courses/{course['id']}/unpublish", headers=teacher)).json()["status"] == "archived"
    assert (await client.post(f"{O}/courses/{course['id']}/submit", headers=teacher)).json()["status"] == "published"
    # A published course can't be deleted, and its published lectures can't either.
    assert (await client.delete(f"{O}/courses/{course['id']}", headers=teacher)).status_code == 409
    lecture = live["sections"][0]["lectures"][0]["id"]
    gone = await client.delete(f"{O}/lectures/{lecture}", headers=teacher)
    assert gone.status_code == 409 and error_code(gone) == "LECTURE_PUBLISHED"

    # Staff can unpublish with a note.
    pulled = (await client.post(f"{P}/courses/{course['id']}/unpublish", headers=ph,
                                json={"note": "Copyright complaint"})).json()
    assert pulled["status"] == "archived" and pulled["review_note"] == "Copyright complaint"

    audit = (await client.get(f"{P}/audit", headers=ph, params={"entity_id": course["id"]})).json()["items"]
    actions = [a["action"] for a in audit]
    for expected in ("course.create", "course.submit", "platform.course.request_changes", "course.withdraw",
                     "platform.course.approve", "course.unpublish", "course.publish", "platform.course.unpublish"):
        assert expected in actions, expected


async def test_curriculum_rules(client: AsyncClient, seed: Seed, teacher: Headers) -> None:
    course = await new_course(client, teacher)
    paid = await client.patch(f"{O}/courses/{course['id']}", headers=teacher, json={"pricing_model": "one_time"})
    assert paid.status_code == 422 and error_code(paid) == "PRICING_INVALID"
    monthly = await client.patch(f"{O}/courses/{course['id']}", headers=teacher, json={"pricing_model": "monthly"})
    assert monthly.status_code == 422      # courses are one-time or free
    exam = await client.patch(f"{O}/courses/{course['id']}", headers=teacher, json={"exam": "al"})
    assert exam.status_code == 422         # no exam fields on a course

    detail = (await client.post(f"{O}/courses/{course['id']}/sections", headers=teacher, json={"title": "One"})).json()
    detail = (await client.post(f"{O}/courses/{course['id']}/sections", headers=teacher, json={"title": "Two"})).json()
    one, two = (s["id"] for s in detail["sections"])
    assert [s["sort_order"] for s in detail["sections"]] == [0, 1]

    empty = await client.post(f"{O}/course-sections/{one}/lectures", headers=teacher,
                              json={"title": "Notes", "lesson_type": "article"})
    assert empty.status_code == 422 and error_code(empty) == "ARTICLE_REQUIRED"
    live = await client.post(f"{O}/course-sections/{one}/lectures", headers=teacher,
                             json={"title": "Zoom", "lesson_type": "live"})
    assert live.status_code == 422         # courses never have live lessons
    detail = (await client.post(f"{O}/course-sections/{one}/lectures", headers=teacher,
                                json={"title": "Intro", "lesson_type": "recorded"})).json()
    lecture = detail["sections"][0]["lectures"][0]
    await client.post(f"{O}/lessons/{lecture['id']}/resources", headers=teacher,
                      json={"media_asset_id": await ready_video(seed.a, 120)})

    # A lecture with a video stays a video lecture; it can move to another section of the same course.
    to_pdf = await client.patch(f"{O}/lectures/{lecture['id']}", headers=teacher, json={"lesson_type": "document"})
    assert to_pdf.status_code == 409 and error_code(to_pdf) == "MEDIA_KIND_INVALID"
    moved = (await client.patch(f"{O}/lectures/{lecture['id']}", headers=teacher, json={"section_id": two})).json()
    assert moved["sections"][1]["lectures"][0]["id"] == lecture["id"]
    assert moved["sections"][1]["lectures"][0]["video_seconds"] == 120

    other = await new_course(client, teacher, "Another course")
    stray = (await client.post(f"{O}/courses/{other['id']}/sections", headers=teacher, json={"title": "X"})).json()
    wrong = await client.patch(f"{O}/lectures/{lecture['id']}", headers=teacher,
                               json={"section_id": stray["sections"][0]["id"]})
    assert wrong.status_code == 422 and error_code(wrong) == "SECTION_INVALID"

    full = await client.delete(f"{O}/course-sections/{two}", headers=teacher)
    assert full.status_code == 409 and error_code(full) == "SECTION_NOT_EMPTY"
    assert (await client.delete(f"{O}/course-sections/{one}", headers=teacher)).status_code == 200
    # A draft that was never published can be deleted with everything in it.
    assert (await client.delete(f"{O}/courses/{course['id']}", headers=teacher)).status_code == 204
    assert (await client.get(f"{O}/courses/{course['id']}", headers=teacher)).status_code == 404


async def test_pending_tenant_cannot_submit(client: AsyncClient, seed: Seed, teacher: Headers) -> None:
    course = await new_course(client, teacher)
    await landing(client, teacher, course["id"])
    await curriculum(client, teacher, seed.a, course["id"])
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE tenants SET status = 'pending' WHERE id = :t"), {"t": seed.a.id})
    try:
        # Draft mode: a pending organization builds courses in its console (/teach/<slug>) but can't submit.
        teach = f"/api/v1/teach/{seed.a.slug}/courses/{course['id']}"
        r = await client.get(teach, headers=teacher)
        assert r.status_code == 200, r.text
        assert {c["key"]: c["ok"] for c in r.json()["checks"]}["tenant_approved"] is False
        refused = await client.post(f"{teach}/submit", headers=teacher)
        assert refused.status_code == 409 and error_code(refused) == "COURSE_NOT_READY"
    finally:
        async with AdminSession() as s, s.begin():
            await s.execute(text("UPDATE tenants SET status = 'active' WHERE id = :t"), {"t": seed.a.id})


# --- courses stay out of the tuition screens (and, since C3, are bought through the cart) -----------

async def test_courses_are_not_classes(client: AsyncClient, sms: FakeSms, seed: Seed, teacher: Headers,
                                       ph: Headers, phones: Any) -> None:  # noqa: F811
    course = await new_course(client, teacher)
    await landing(client, teacher, course["id"])
    await curriculum(client, teacher, seed.a, course["id"])
    await client.post(f"{O}/courses/{course['id']}/submit", headers=teacher)
    await client.post(f"{P}/courses/{course['id']}/decision", headers=ph, json={"decision": "approve"})

    listed = (await client.get(f"{O}/classes", headers=teacher)).json()["items"]
    assert course["id"] not in {c["id"] for c in listed}
    assert (await client.get(f"{O}/classes/{course['id']}", headers=teacher)).status_code == 404
    assert (await client.patch(f"{O}/classes/{course['id']}", headers=teacher, json={"title": "x"})).status_code == 404
    assert (await client.get(f"{O}/classes/{course['id']}/lessons", headers=teacher)).status_code == 404
    lecture = (await client.get(f"{O}/courses/{course['id']}", headers=teacher)).json()["sections"][0]["lectures"][0]
    assert (await client.patch(f"{O}/lessons/{lecture['id']}", headers=teacher,
                               json={"lesson_type": "live"})).status_code == 404
    async with AppSession() as s:
        assert (await s.execute(text("SELECT count(*) FROM public_classes WHERE id = :id"),
                                {"id": course["id"]})).scalar_one() == 0

    student = await main_login(client, sms, phones())
    added = await client.post("/api/v1/me/cart/items", headers=student, json={"class_id": course["id"]})
    assert added.status_code == 201, added.text      # bought like a one-time class (step C3)


# --- slugs, permissions, isolation ----------------------------------------------------------------

async def test_slugs_are_unique_across_tenants(client: AsyncClient, sms: FakeSms, seed: Seed,
                                               teacher: Headers) -> None:
    a = await new_course(client, teacher, "Python for Beginners")
    b_teacher = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    b = await new_course(client, b_teacher, "Python for Beginners")
    assert a["slug"] == "python-for-beginners" or a["slug"].startswith("python-for-beginners")
    assert b["slug"] != a["slug"]
    clash = await client.patch(f"{O}/courses/{b['id']}", headers=b_teacher, json={"slug": a["slug"]})
    assert clash.status_code == 409 and error_code(clash) == "SLUG_TAKEN"
    # Tenant B sees nothing of tenant A's course.
    assert (await client.get(f"{O}/courses/{a['id']}", headers=b_teacher)).status_code == 404
    assert a["id"] not in {c["id"] for c in (await client.get(f"{O}/courses", headers=b_teacher)).json()}
    sections = (await client.post(f"{O}/courses/{a['id']}/sections", headers=teacher, json={"title": "S"})).json()
    assert (await client.post(f"{O}/course-sections/{sections['sections'][0]['id']}/lectures", headers=b_teacher,
                              json={"title": "x", "lesson_type": "recorded"})).status_code == 404


async def test_teachers_see_only_their_courses(client: AsyncClient, sms: FakeSms, seed: Seed, teacher: Headers,
                                               members: AddMember) -> None:
    mine = await new_course(client, teacher)
    other = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    assert (await client.get(f"{O}/courses/{mine['id']}", headers=other)).status_code == 404
    assert (await client.get(f"{O}/courses", headers=other)).json() == []
    assert mine["id"] in {c["id"] for c in (await client.get(f"{O}/courses", headers=owner)).json()}
    reassign = await client.patch(f"{O}/courses/{mine['id']}", headers=teacher,
                                  json={"teacher_member_id": str(uuid4())})
    assert reassign.status_code == 403


# --- categories ----------------------------------------------------------------------------------------

async def test_categories(client: AsyncClient, ph: Headers, new_categories: list[str]) -> None:  # noqa: F811
    public = (await client.get("/api/v1/market/course-categories")).json()
    assert {"it-networking", "software-development", "languages"} <= {c["slug"] for c in public}

    top = f"t-{uuid4().hex[:8]}"
    new_categories.append(top)
    parent = (await client.post(f"{P}/course-categories", headers=ph,
                                json={"slug": top, "name_en": "Cloud", "name_si": "ක්ලවුඩ්"})).json()
    sub = (await client.post(f"{P}/course-categories", headers=ph,
                             json={"slug": f"{top}-aws", "name_en": "AWS", "parent_id": parent["id"]})).json()
    new_categories.append(sub["slug"])
    deep = await client.post(f"{P}/course-categories", headers=ph,
                             json={"slug": f"{top}-ec2", "name_en": "EC2", "parent_id": sub["id"]})
    assert deep.status_code == 422 and error_code(deep) == "CATEGORY_DEPTH"
    again = await client.post(f"{P}/course-categories", headers=ph, json={"slug": top, "name_en": "Dup"})
    assert again.status_code == 409

    hidden = (await client.patch(f"{P}/course-categories/{sub['id']}", headers=ph, json={"is_active": False})).json()
    assert hidden["is_active"] is False
    public = (await client.get("/api/v1/market/course-categories")).json()
    assert parent["slug"] in {c["slug"] for c in public} and sub["slug"] not in {c["slug"] for c in public}
    assert (await client.patch(f"{P}/course-categories/{sub['id']}", headers=ph,
                               json={"slug": "x"})).status_code == 422          # the address is fixed


async def test_new_reserved_slugs(client: AsyncClient) -> None:
    async with AppSession() as s:
        assert (await s.execute(text(
            "SELECT bool_and(is_reserved_slug(x)) FROM unnest(ARRAY['course','courses','instructor','certificates',"
            "'wishlist','categories','checkouts']) x"))).scalar_one()


def test_application_offers() -> None:
    base: dict[str, Any] = {"kind": "individual", "org_name": "Nimal IT", "payout_bank_name": "BOC",
                            "payout_account_name": "Nimal", "payout_account_number": "12345678", "accept_terms": True}
    assert ApplicationFields.model_validate({**base, "offers": "courses"}).subject_ids == []
    with pytest.raises(ValueError):
        ApplicationFields.model_validate({**base, "offers": "both"})       # tuition needs a subject
    assert ApplicationFields.model_validate({**base, "subject_ids": [str(uuid4())]}).offers == "classes"


