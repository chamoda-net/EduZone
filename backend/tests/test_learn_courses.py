"""Courses, step C3 (docs/COURSES.md): buying and enrolling, the course player's data, lecture completion and
progress, "My courses", and what stays closed."""

from collections.abc import Callable
from typing import Any

import pytest
from httpx import AsyncClient

from tests.conftest import FakeSms, Seed
from tests.helpers import error_code
from tests.test_cart import pay
from tests.test_courses import O, P, curriculum, landing, new_course, teacher  # noqa: F401  (fixtures)
from tests.test_learn import main_login
from tests.test_market_courses import live_course
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
L = "/api/v1/learn"
Phones = Callable[[], str]


@pytest.fixture
async def course(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers) -> dict[str, Any]:  # noqa: F811
    """A paid course (Rs. 3,000) on the marketplace: 2 sections, 4 videos of 8 minutes and an article; the first
    lecture is a free preview."""
    return await live_course(client, seed, teacher, ph, "Networking Basics")


@pytest.fixture
async def student(client: AsyncClient, sms: FakeSms, phones: Phones) -> Headers:
    return await main_login(client, sms, phones())


async def buy(client: AsyncClient, h: Headers, course_id: str, amount: int = 300000) -> None:
    added = await client.post("/api/v1/me/cart/items", headers=h, json={"class_id": course_id})
    assert added.status_code == 201, added.text
    _, form = await pay(client, h, amount=amount)
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "paid"


def lectures(view: dict[str, Any]) -> list[dict[str, Any]]:
    return [lec for s in view["sections"] for lec in s["lectures"]]


async def test_buy_watch_and_complete(client: AsyncClient, course: dict[str, Any], student: Headers) -> None:
    cid = course["id"]
    before = (await client.get(f"{L}/courses/{cid}", headers=student)).json()
    assert before["has_access"] is False and before["welcome_message"] is None
    assert [lec["unlocked"] for lec in lectures(before)] == [True, False, False, False, False]
    assert before["progress"] == {"completed": 0, "total": 5, "percent": 0}
    article = lectures(before)[-1]
    locked = (await client.get(f"{L}/lectures/{article['id']}", headers=student)).json()
    assert locked["unlocked"] is False and locked["article_body"] is None and locked["resources"] == []
    refused = await client.post(f"{L}/lectures/{article['id']}/complete", headers=student)
    assert refused.status_code == 403

    # Bought like any one-time class: one cart, one payment, a lifetime grant.
    await buy(client, student, cid)
    view = (await client.get(f"{L}/courses/{cid}", headers=student)).json()
    assert view["has_access"] and view["welcome_message"] == "Welcome!" and view["completion_message"] is None
    assert all(lec["unlocked"] for lec in lectures(view))
    assert view["next_lecture_id"] == lectures(view)[0]["id"]
    again = await client.post("/api/v1/me/cart/items", headers=student, json={"class_id": cid})
    assert again.status_code == 409 and error_code(again) == "ALREADY_HAS_ACCESS"

    # An article: its text now, and "Mark as complete" (and un-mark).
    detail = (await client.get(f"{L}/lectures/{article['id']}", headers=student)).json()
    assert detail["article_body"].startswith("# OSPF") and detail["prev_id"] and detail["next_id"] is None
    done = (await client.post(f"{L}/lectures/{article['id']}/complete", headers=student)).json()
    assert done["completed"] and done["progress"] == {"completed": 1, "total": 5, "percent": 20}
    undone = (await client.delete(f"{L}/lectures/{article['id']}/complete", headers=student)).json()
    assert undone["progress"]["completed"] == 0
    await client.post(f"{L}/lectures/{article['id']}/complete", headers=student)

    # A video completes itself once it passes 90%.
    first = (await client.get(f"{L}/lectures/{lectures(view)[0]['id']}", headers=student)).json()
    video = first["resources"][0]
    assert (await client.post(f"{L}/resources/{video['id']}/open", headers=student)).status_code == 200
    report = await client.post(f"{L}/resources/{video['id']}/progress", headers=student,
                               json={"position_seconds": 450, "watched_seconds": 30})
    assert report.json()["completed"] is True
    view = (await client.get(f"{L}/courses/{cid}", headers=student)).json()
    assert lectures(view)[0]["completed"] and view["progress"]["completed"] == 2
    assert view["next_lecture_id"] == lectures(view)[1]["id"]

    # The rest by hand: 100%, and the congratulations message.
    for lec in lectures(view)[1:4]:
        await client.post(f"{L}/lectures/{lec['id']}/complete", headers=student)
    view = (await client.get(f"{L}/courses/{cid}", headers=student)).json()
    assert view["progress"] == {"completed": 5, "total": 5, "percent": 100}
    assert view["completion_message"] == "Well done!"

    mine = (await client.get(f"{L}/courses", headers=student)).json()
    assert [c["id"] for c in mine] == [cid] and mine[0]["progress"]["percent"] == 100
    # Courses are not tuition classes in "My classes".
    assert cid not in {c["class"]["id"] for c in (await client.get(f"{L}/classes", headers=student)).json()}


async def test_free_course_enrolment(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers,  # noqa: F811
                                     student: Headers, course: dict[str, Any]) -> None:
    free = await new_course(client, teacher, "Free Linux Basics")
    await landing(client, teacher, free["id"])
    await client.patch(f"{O}/courses/{free['id']}", headers=teacher,
                       json={"pricing_model": "free", "one_time_price_cents": None})
    await curriculum(client, teacher, seed.a, free["id"])
    await client.post(f"{O}/courses/{free['id']}/submit", headers=teacher)
    await client.post(f"{P}/courses/{free['id']}/decision", headers=ph, json={"decision": "approve"})

    cart = await client.post("/api/v1/me/cart/items", headers=student, json={"class_id": free["id"]})
    assert cart.status_code == 409 and error_code(cart) == "FREE_CLASS"
    enrolled = (await client.post(f"{L}/courses/{free['id']}/enroll", headers=student)).json()
    assert enrolled["has_access"] and all(lec["unlocked"] for lec in lectures(enrolled))
    assert (await client.post(f"{L}/courses/{free['id']}/enroll", headers=student)).status_code == 200  # idempotent
    paid = await client.post(f"{L}/courses/{course['id']}/enroll", headers=student)
    assert paid.status_code == 409 and error_code(paid) == "NOT_FREE"
    assert {c["id"] for c in (await client.get(f"{L}/courses", headers=student)).json()} == {free["id"]}


async def test_what_stays_closed(client: AsyncClient, seed: Seed, teacher: Headers, ph: Headers,  # noqa: F811
                                 sms: FakeSms, phones: Phones, student: Headers, course: dict[str, Any]) -> None:
    await buy(client, student, course["id"])
    stranger = await main_login(client, sms, phones())

    # Unpublished: buyers keep the course, nobody else can open it.
    await client.post(f"{O}/courses/{course['id']}/unpublish", headers=teacher)
    assert (await client.get(f"{L}/courses/{course['id']}", headers=student)).json()["has_access"]
    assert (await client.get(f"{L}/courses/{course['id']}", headers=stranger)).status_code == 404
    assert (await client.post("/api/v1/me/cart/items", headers=stranger,
                              json={"class_id": course["id"]})).status_code in (404, 409)

    # A course waiting for review shows nothing to students, not even its free preview.
    draft = await new_course(client, teacher, "In Review Course")
    await landing(client, teacher, draft["id"])
    d = await curriculum(client, teacher, seed.a, draft["id"])
    preview = d["sections"][0]["lectures"][0]
    await client.patch(f"{O}/lectures/{preview['id']}", headers=teacher, json={"is_free_preview": True})
    assert (await client.post(f"{O}/courses/{draft['id']}/submit", headers=teacher)).json()["status"] == "in_review"
    assert (await client.get(f"{L}/courses/{draft['id']}", headers=stranger)).status_code == 404
    assert (await client.get(f"{L}/lectures/{preview['id']}", headers=stranger)).status_code == 404

    # Another student's progress is theirs alone.
    article = lectures((await client.get(f"{L}/courses/{course['id']}", headers=student)).json())[-1]
    await client.post(f"{L}/lectures/{article['id']}/complete", headers=student)
    assert (await client.get(f"{L}/courses", headers=stranger)).json() == []
