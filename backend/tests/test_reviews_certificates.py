"""Courses, step C4 (docs/COURSES.md C.5 and C.6): reviews (student, instructor reply, staff moderation, the public
list) and certificates (issued at 100% of a paid course only, snapshots, public verify, PDF)."""

from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.tenancy import tenant_transaction
from tests.conftest import FakeSms, Seed
from tests.helpers import auth_headers
from tests.test_courses import O, P, curriculum, landing, new_course, teacher  # noqa: F401  (fixtures)
from tests.test_learn import main_login, user_id_of
from tests.test_learn_courses import buy, lectures
from tests.test_market_courses import live_course
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
L = "/api/v1/learn"
M = "/api/v1/market"
Phones = Callable[[], str]


@pytest.fixture
async def course(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers) -> dict[str, Any]:  # noqa: F811
    return await live_course(client, seed, teacher, ph, "Routing Deep Dive")


async def complete_all(client: AsyncClient, h: Headers, course_id: str) -> dict[str, Any]:
    view = (await client.get(f"{L}/courses/{course_id}", headers=h)).json()
    for lec in lectures(view):
        r = await client.post(f"{L}/lectures/{lec['id']}/complete", headers=h)
        assert r.status_code == 200, r.text
    return (await client.get(f"{L}/courses/{course_id}", headers=h)).json()


# --- reviews -------------------------------------------------------------------------------------------

async def test_reviews(client: AsyncClient, sms: FakeSms, phones: Phones, seed: Seed, teacher: Headers,  # noqa: F811
                       ph: Headers, course: dict[str, Any]) -> None:
    cid, slug = course["id"], course["slug"]
    first, second = await main_login(client, sms, phones()), await main_login(client, sms, phones())
    nope = await client.put(f"{L}/courses/{cid}/review", headers=first, json={"rating": 5})
    assert nope.status_code == 403            # only students of the course
    await buy(client, first, cid)
    await buy(client, second, cid)

    mine = (await client.put(f"{L}/courses/{cid}/review", headers=first,
                             json={"rating": 5, "comment": "  Clear and practical.  "})).json()
    assert mine["rating"] == 5 and mine["comment"] == "Clear and practical." and mine["status"] == "visible"
    await client.put(f"{L}/courses/{cid}/review", headers=second, json={"rating": 2})
    edited = (await client.put(f"{L}/courses/{cid}/review", headers=second, json={"rating": 3})).json()
    assert edited["rating"] == 3                # one review per student, editable
    assert (await client.put(f"{L}/courses/{cid}/review", headers=first, json={"rating": 6})).status_code == 422

    page = (await client.get(f"{M}/course/{slug}/reviews")).json()
    assert page["summary"] == {"average": 4.0, "count": 2, "distribution": {"5": 1, "4": 0, "3": 1, "2": 0, "1": 0}}
    assert page["items"][0]["comment"] == "Clear and practical." and page["items"][0]["reviewer"] == "Test S."
    card = (await client.get(f"{M}/course/{slug}")).json()["course"]
    assert (card["rating_avg"], card["rating_count"]) == (4.0, 2)
    assert (await client.get(f"{L}/courses/{cid}", headers=first)).json()["my_rating"] == 5

    # The instructor replies; another organization's teacher can't.
    review_id = mine["id"]
    staff = (await client.get(f"{O}/courses/{cid}/reviews", headers=teacher)).json()
    assert {r["rating"] for r in staff} == {5, 3}
    replied = (await client.put(f"{O}/course-reviews/{review_id}/reply", headers=teacher,
                                json={"reply": "Thank you!"})).json()
    assert replied["instructor_reply"] == "Thank you!" and replied["replied_at"]
    other = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    assert (await client.put(f"{O}/course-reviews/{review_id}/reply", headers=other,
                             json={"reply": "x"})).status_code == 404
    assert (await client.get(f"{M}/course/{slug}/reviews")).json()["items"][0]["instructor_reply"] == "Thank you!"

    # EduZone staff hide a review: off the page and out of the rating; shown again restores it.
    second_id = next(r["id"] for r in staff if r["rating"] == 3)
    hidden = await client.post(f"{P}/course-reviews/{second_id}/hide", headers=ph, json={"reason": "Off-topic"})
    assert hidden.status_code == 200 and hidden.json()["status"] == "hidden"
    assert (await client.get(f"{M}/course/{slug}/reviews")).json()["summary"]["count"] == 1
    assert (await client.get(f"{M}/course/{slug}")).json()["course"]["rating_avg"] == 5.0
    assert any(r["id"] == second_id for r in (await client.get(f"{P}/course-reviews", headers=ph,
                                                                 params={"status": "hidden"})).json())
    await client.post(f"{P}/course-reviews/{second_id}/show", headers=ph)
    assert (await client.get(f"{M}/course/{slug}")).json()["course"]["rating_count"] == 2

    # Deleting one's own review recomputes the rating too.
    assert (await client.delete(f"{L}/courses/{cid}/review", headers=second)).status_code == 204
    assert (await client.get(f"{M}/course/{slug}")).json()["course"]["rating_count"] == 1


# --- certificates ----------------------------------------------------------------------------------------

async def test_certificate_for_a_bought_course(client: AsyncClient, sms: FakeSms, phones: Phones, teacher: Headers,  # noqa: F811
                                               course: dict[str, Any]) -> None:
    cid = course["id"]
    student = await main_login(client, sms, phones())
    await buy(client, student, cid)
    view = (await client.get(f"{L}/courses/{cid}", headers=student)).json()
    assert view["certificate_no"] is None
    done = await complete_all(client, student, cid)
    number = done["certificate_no"]
    assert number and number.startswith("EZCERT-") and len(number) == 16

    mine = (await client.get(f"{L}/certificates", headers=student)).json()
    assert [c["certificate_no"] for c in mine] == [number]
    assert mine[0]["course_title"] == "Routing Deep Dive" and mine[0]["verify_path"] == f"/certificates/{number}"

    # Public verification shows the snapshot; later edits to the course don't change it.
    await client.patch(f"{O}/courses/{cid}", headers=teacher, json={"title": "Routing Deep Dive (2027 edition)"})
    check = (await client.get(f"{M}/certificates/{number.lower()}")).json()
    assert check["valid"] and check["course_title"] == "Routing Deep Dive" and check["student_name"] == "Test Student"
    assert (await client.get(f"{M}/certificates/EZCERT-AAAA-AAAA")).status_code == 404

    pdf = await client.get(f"{M}/certificates/{number}/pdf", headers={"host": "localhost"})
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF")

    # Un-marking and re-completing never issues a second certificate.
    last = lectures(done)[-1]
    await client.delete(f"{L}/lectures/{last['id']}/complete", headers=student)
    await client.post(f"{L}/lectures/{last['id']}/complete", headers=student)
    assert [c["certificate_no"] for c in (await client.get(f"{L}/certificates", headers=student)).json()] == [number]


async def test_no_certificate_without_buying(client: AsyncClient, sms: FakeSms, phones: Phones, seed: Seed,
                                             course: dict[str, Any]) -> None:
    """A course given by the teacher (scholarship) is completed but earns no certificate (paid courses only)."""
    phone = phones()
    student = await main_login(client, sms, phone)
    user_id = await user_id_of(phone)
    async with tenant_transaction(seed.a.id) as s:
        member = (await s.execute(text("""
            INSERT INTO tenant_members (tenant_id, user_id, role) VALUES (current_tenant_id(), :u, 'student')
            RETURNING id
        """), {"u": user_id})).scalar_one()
        await s.execute(text("""
            INSERT INTO access_grants (tenant_id, student_member_id, class_id, source)
            VALUES (current_tenant_id(), :m, :c, 'scholarship')
        """), {"m": member, "c": course["id"]})
    done = await complete_all(client, student, course["id"])
    assert done["progress"]["percent"] == 100 and done["certificate_no"] is None
    assert (await client.get(f"{L}/certificates", headers=student)).json() == []
    # Reviewing is allowed to anyone with access, though.
    assert (await client.put(f"{L}/courses/{course['id']}/review", headers=student,
                             json={"rating": 4})).status_code == 200
    missing = await client.get(f"{L}/courses/{course['id']}/review", headers=await main_login(client, sms, phones()))
    assert missing.status_code == 200 and missing.json() is None


async def test_public_reviews_view_is_narrow() -> None:
    from app.core.db import AppSession

    async with AppSession() as s:
        columns = set((await s.execute(text("SELECT * FROM public_course_reviews LIMIT 0"))).keys())
        # The app role reads no reviews or certificates outside the narrow paths.
        assert (await s.execute(text("SELECT count(*) FROM course_reviews"))).scalar_one() == 0
        assert (await s.execute(text("SELECT count(*) FROM certificates"))).scalar_one() == 0
    assert columns == {"id", "course_id", "rating", "comment", "instructor_reply", "replied_at", "created_at",
                       "updated_at", "reviewer"}
