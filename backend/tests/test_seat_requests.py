"""Seats, step S3 (docs/SEATS.md): seat requests, the notify list, what students see, the public seat information."""

import asyncio
from collections.abc import Callable
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.config import get_settings
from app.core.db import AdminSession, AppSession
from app.core.tenancy import tenant_transaction, user_transaction
from tests.conftest import AddMember, FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_cart import add, one_time_class
from tests.test_checkout import checkout, notify, payment_key
from tests.test_learn import main_login, user_id_of
from tests.test_learning import member_id, monthly_class
from tests.test_market import published
from tests.test_seat_renewals import open_december, patch_month, renewal_passed
from tests.test_seats import (  # noqa: F401  (fixtures)
    NewStudent,
    buy,
    end_holds,
    give,
    new_student,
    seats,
    seats_on,
    settings,
    slow_check,
    teacher,
)

Headers = dict[str, str]
L = "/api/v1/learn"
M = "/api/v1/market"


async def ask(client: AsyncClient, h: Headers, class_id: str, month_id: str | None, note: str | None = None) -> Any:
    return await client.post(f"{L}/classes/{class_id}/seat-request", headers=h,
                             json={"class_month_id": month_id, "note": note})


async def decide(client: AsyncClient, teacher: Headers, request_id: str, decision: str, **extra: Any) -> Any:
    return await client.post(f"/api/v1/org/seat-requests/{request_id}/decision", headers=teacher,
                             json={"decision": decision, **extra})


async def inbox(client: AsyncClient, teacher: Headers, status: str = "pending") -> list[dict[str, Any]]:
    r = await client.get("/api/v1/org/seat-requests", headers=teacher, params={"status": status})
    assert r.status_code == 200, r.text
    return r.json()


async def view(client: AsyncClient, h: Headers, class_id: str) -> dict[str, Any]:
    r = await client.get(f"{L}/classes/{class_id}", headers=h)
    assert r.status_code == 200, r.text
    return r.json()


async def month_seat(client: AsyncClient, h: Headers, class_id: str, month: str = "2026-11-01") -> Any:
    return next(m["seat"] for m in (await view(client, h, class_id))["months"] if m["month_start"] == month)


async def expire_requests(class_id: str) -> None:
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE seat_requests SET held_until = now() - interval '1 second' WHERE class_id = :c "
                             "AND status = 'approved'"), {"c": class_id})


async def ask_class(client: AsyncClient, teacher: Headers, **extra: Any) -> tuple[str, str, dict[str, Any]]:  # noqa: F811
    k = await monthly_class(client, teacher, **{"seat_limit": 2, "registration": "ask", **extra})
    return k["class"]["id"], k["months"]["open"]["id"], k


# --- asking --------------------------------------------------------------------------------------------

async def test_ask_accept_pay(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    cid, month, _ = await ask_class(client, teacher)
    h = await new_student()
    assert (await month_seat(client, h, cid))["problem"] == "SEAT_REQUEST_REQUIRED"
    made = await ask(client, h, cid, month, "  I'm at Royal College  ")
    assert made.status_code == 201, made.text
    assert made.json()["status"] == "pending" and made.json()["student_note"] == "I'm at Royal College"
    assert made.json()["month_start"] == "2026-11-01"
    assert error_code(await ask(client, h, cid, month)) == "REQUEST_EXISTS"
    # A request holds nothing.
    assert (await seats(client, teacher, cid, month))["taken"] == 0
    assert error_code(await checkout(client, h, cid, month)) == "SEAT_REQUEST_REQUIRED"

    (row,) = await inbox(client, teacher)
    assert row["student_note"] == "I'm at Royal College" and row["seats_free"] == 2 and row["class_title"] == "A/L Physics"
    out = (await decide(client, teacher, row["id"], "approve", note="Welcome")).json()
    assert out["status"] == "approved" and out["decision_note"] == "Welcome"
    left = datetime.fromisoformat(out["held_until"]) - datetime.fromisoformat(out["decided_at"])
    assert timedelta(hours=47, minutes=59) < left <= timedelta(hours=48, seconds=5)
    assert await inbox(client, teacher) == []
    s = await seats(client, teacher, cid, month)
    assert s["taken"] == 1 and s["seats"][0]["kind"] == "accepted" and s["seats"][0]["held_until"] == out["held_until"]
    seen = await month_seat(client, h, cid)
    assert seen["problem"] is None and seen["request"]["status"] == "approved" and seen["request"]["decision_note"] == "Welcome"
    mine = (await client.get(f"{L}/seat-requests", headers=h)).json()
    assert [r["status"] for r in mine] == ["approved"] and mine[0]["org"]["slug"]

    # Paying works even when registration closes meanwhile; the seat is counted once, and the request is used.
    await settings(client, teacher, cid, registration="closed")
    out = await checkout(client, h, cid, month)
    assert out.status_code == 201
    s = await seats(client, teacher, cid, month)
    assert s["taken"] == 1 and s["seats"][0]["kind"] == "paying"
    await notify(client, payment_key(out.json()))
    s = await seats(client, teacher, cid, month)
    assert s["taken"] == 1 and s["seats"][0]["kind"] == "access"
    assert [r["status"] for r in await inbox(client, teacher, "used")] == ["used"]
    assert (await client.get(f"{L}/seat-requests", headers=h)).json() == []


async def test_an_accepted_request_expires(client: AsyncClient, teacher: Headers,  # noqa: F811
                                           new_student: NewStudent) -> None:  # noqa: F811
    cid, month, _ = await ask_class(client, teacher, seat_limit=1)
    h = await new_student()
    rid = (await ask(client, h, cid, month)).json()["id"]
    await decide(client, teacher, rid, "approve")
    # The seat is theirs: nobody else can be accepted or pay.
    other = await new_student()
    assert error_code(await ask(client, other, cid, month)) == "CLASS_FULL"
    await expire_requests(cid)
    assert (await seats(client, teacher, cid, month))["taken"] == 0
    seen = await month_seat(client, h, cid)
    assert seen["request"]["status"] == "expired" and seen["problem"] == "SEAT_REQUEST_REQUIRED"
    assert error_code(await checkout(client, h, cid, month)) == "SEAT_REQUEST_REQUIRED"
    assert [r["status"] for r in await inbox(client, teacher, "expired")] == ["expired"]
    assert await inbox(client, teacher, "approved") == []
    # They may ask again (the same request starts over), or the teacher accepts again.
    again = (await ask(client, h, cid, month, "Sorry, I was ill")).json()
    assert again["id"] == rid and again["status"] == "pending" and again["held_until"] is None
    await decide(client, teacher, rid, "approve")
    await expire_requests(cid)
    assert (await decide(client, teacher, rid, "approve")).json()["status"] == "approved"


async def test_refusing(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    cid, month, k = await ask_class(client, teacher)
    h = await new_student()
    rid = (await ask(client, h, cid, month)).json()["id"]
    assert (await decide(client, teacher, rid, "reject", note="Too advanced for now")).json()["status"] == "rejected"
    assert (await month_seat(client, h, cid))["request"]["decision_note"] == "Too advanced for now"
    assert error_code(await ask(client, h, cid, month)) == "REQUEST_REJECTED"
    assert error_code(await decide(client, teacher, rid, "reject")) == "REQUEST_DECIDED"
    # Another month is another request.
    december = await open_december(client, teacher, k)
    assert (await ask(client, h, cid, december)).status_code == 201
    # The teacher can change their mind, and take an unpaid acceptance back.
    assert (await decide(client, teacher, rid, "approve")).status_code == 200
    assert error_code(await decide(client, teacher, rid, "approve")) == "REQUEST_DECIDED"
    assert (await seats(client, teacher, cid, month))["taken"] == 1
    assert (await decide(client, teacher, rid, "reject")).status_code == 200
    assert (await seats(client, teacher, cid, month))["taken"] == 0


async def test_withdrawing(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    cid, month, _ = await ask_class(client, teacher)
    h = await new_student()
    url = f"{L}/classes/{cid}/seat-request"
    assert (await client.delete(url, headers=h, params={"class_month_id": month})).status_code == 404
    rid = (await ask(client, h, cid, month)).json()["id"]
    assert (await client.delete(url, headers=h, params={"class_month_id": month})).status_code == 204
    assert await inbox(client, teacher) == [] and (await month_seat(client, h, cid))["request"] is None
    assert error_code(await decide(client, teacher, rid, "approve")) == "REQUEST_DECIDED"
    # Asking again is fine; withdrawing an acceptance frees the seat.
    assert (await ask(client, h, cid, month)).json()["id"] == rid
    await decide(client, teacher, rid, "approve")
    await client.delete(url, headers=h, params={"class_month_id": month})
    assert (await seats(client, teacher, cid, month))["taken"] == 0


async def test_asking_only_when_needed(client: AsyncClient, sms: FakeSms, teacher: Headers,  # noqa: F811
                                       new_student: NewStudent, phones: Callable[[], str]) -> None:  # noqa: F811
    cid, month, k = await ask_class(client, teacher, seat_limit=1)
    h = await new_student()
    for bad, code in ((None, "MONTH_REQUIRED"), (k["months"]["upcoming"]["id"], "MONTH_NOT_OPEN"),
                      (k["months"]["closed"]["id"], "MONTH_NOT_OPEN"), (str(uuid4()), "MONTH_INVALID")):
        assert error_code(await ask(client, h, cid, bad)) == code
    assert (await ask(client, h, str(uuid4()), month)).status_code == 404
    assert (await ask(client, h, cid, month, "x" * 501)).status_code == 422
    await settings(client, teacher, cid, registration="open")
    assert error_code(await ask(client, h, cid, month)) == "REQUEST_NOT_NEEDED"
    await settings(client, teacher, cid, registration="closed")
    assert error_code(await ask(client, h, cid, month)) == "REGISTRATION_CLOSED"
    await settings(client, teacher, cid, registration="open")
    inside = await new_student()
    await buy(client, inside, cid, month)
    await settings(client, teacher, cid, registration="ask")
    assert error_code(await ask(client, inside, cid, month)) == "ALREADY_HAS_ACCESS"
    assert error_code(await ask(client, h, cid, month)) == "CLASS_FULL"
    # A continuing student needs nobody's permission.
    december = await open_december(client, teacher, k)
    await renewal_passed(december)
    assert error_code(await ask(client, inside, cid, december)) == "REQUEST_NOT_NEEDED"
    # Like paying, it takes a verified phone; and a published class.
    no_phone = await main_login(client, sms, phones())
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE users SET phone_verified_at = NULL WHERE id = (SELECT user_id FROM user_sessions "
                             "ORDER BY created_at DESC LIMIT 1)"))
    assert error_code(await ask(client, no_phone, cid, december)) == "PHONE_NOT_VERIFIED"
    await settings(client, teacher, cid, status="archived")
    assert (await ask(client, h, cid, december)).status_code == 404
    assert (await client.post(f"{L}/classes/{cid}/seat-request", json={})).status_code == 401


async def test_accepting_into_a_full_class(client: AsyncClient, teacher: Headers,  # noqa: F811
                                           new_student: NewStudent) -> None:  # noqa: F811
    cid, month, _ = await ask_class(client, teacher, seat_limit=1)
    ids = [(await ask(client, await new_student(), cid, month)).json()["id"] for _ in range(2)]
    assert (await decide(client, teacher, ids[0], "approve")).status_code == 200
    assert error_code(await decide(client, teacher, ids[1], "approve")) == "CLASS_FULL"
    assert (await inbox(client, teacher))[0]["seats_free"] == 0
    await settings(client, teacher, cid, seat_limit=2)
    assert (await decide(client, teacher, ids[1], "approve")).status_code == 200


async def test_two_staff_accept_the_last_seat(client: AsyncClient, sms: FakeSms, seed: Seed, teacher: Headers,  # noqa: F811
                                              members: AddMember, new_student: NewStudent,  # noqa: F811
                                              monkeypatch: pytest.MonkeyPatch) -> None:
    from app.modules.seats import service as seats_service

    real = seats_service.seating

    async def slow(*args: Any) -> Any:
        out = await real(*args)
        await asyncio.sleep(0.2)
        return out

    cid, month, _ = await ask_class(client, teacher, seat_limit=1)
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    ids = [(await ask(client, await new_student(), cid, month)).json()["id"] for _ in range(2)]
    monkeypatch.setattr(seats_service, "seating", slow)
    results = await asyncio.gather(decide(client, teacher, ids[0], "approve"), decide(client, owner, ids[1], "approve"))
    monkeypatch.setattr(seats_service, "seating", real)
    assert sorted(r.status_code for r in results) == [200, 409]
    assert (await seats(client, teacher, cid, month))["taken"] == 1


async def test_accepting_needs_an_open_month_and_an_active_student(client: AsyncClient, seed: Seed,
                                                                   teacher: Headers,  # noqa: F811
                                                                   new_student: NewStudent) -> None:  # noqa: F811
    cid, month, _ = await ask_class(client, teacher)
    h = await new_student()
    rid = (await ask(client, h, cid, month)).json()["id"]
    member = await member_id(client, h)
    async with tenant_transaction(seed.a.id) as s:
        await s.execute(text("UPDATE tenant_members SET status = 'suspended' WHERE id = :m"), {"m": member})
    assert error_code(await decide(client, teacher, rid, "approve")) == "STUDENT_INVALID"
    async with tenant_transaction(seed.a.id) as s:
        await s.execute(text("UPDATE tenant_members SET status = 'active' WHERE id = :m"), {"m": member})
    await patch_month(client, teacher, month, status="closed")
    assert error_code(await decide(client, teacher, rid, "approve")) == "MONTH_NOT_OPEN"
    assert (await decide(client, teacher, rid, "reject")).status_code == 200


async def test_who_decides(client: AsyncClient, sms: FakeSms, seed: Seed, teacher: Headers,  # noqa: F811
                           members: AddMember, new_student: NewStudent) -> None:  # noqa: F811
    cid, month, _ = await ask_class(client, teacher)
    h = await new_student()
    rid = (await ask(client, h, cid, month)).json()["id"]
    other_teacher = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    admin = await auth_headers(client, sms, seed.a, await members(seed.a, "admin"))
    other_org = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    assert await inbox(client, other_teacher) == [] and await inbox(client, other_org) == []
    assert (await client.get("/api/v1/org/seat-requests", headers=h)).status_code == 403
    for who, status in ((other_teacher, 404), (other_org, 404), (h, 403)):
        assert (await decide(client, who, rid, "approve")).status_code == status
    assert len(await inbox(client, admin)) == 1
    assert (await decide(client, admin, rid, "approve")).status_code == 200
    assert (await decide(client, teacher, rid, "maybe")).status_code == 422
    async with AdminSession() as s:
        assert (await s.execute(text("SELECT action FROM audit_logs WHERE entity_id = :i"), {"i": rid})).scalars().all() == [
            "seat_request.approve"]


async def test_free_and_one_time_classes(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    free = (await client.post("/api/v1/org/classes", headers=teacher, json={
        "title": "Free revision", "pricing_model": "free", "seat_limit": 1, "registration": "ask"})).json()
    await settings(client, teacher, free["id"], status="published")
    h = await new_student()
    join = f"{L}/classes/{free['id']}/enroll"
    assert (await view(client, h, free["id"]))["seat"]["problem"] == "SEAT_REQUEST_REQUIRED"
    assert error_code(await client.post(join, headers=h)) == "SEAT_REQUEST_REQUIRED"
    assert error_code(await ask(client, h, free["id"], str(uuid4()))) == "MONTH_INVALID"
    rid = (await ask(client, h, free["id"], None)).json()["id"]
    await decide(client, teacher, rid, "approve")
    joined = (await client.post(join, headers=h)).json()
    assert joined["has_class_access"] is True and joined["seat"] is None
    s = await seats(client, teacher, free["id"])
    assert s["taken"] == 1 and s["seats"][0]["kind"] == "access"
    assert len(await inbox(client, teacher, "used")) == 1
    # Leaving and coming back means asking again.
    await client.delete(join, headers=h)
    assert error_code(await client.post(join, headers=h)) == "SEAT_REQUEST_REQUIRED"
    assert (await ask(client, h, free["id"], None)).json()["id"] == rid

    once = await one_time_class(client, teacher)
    await settings(client, teacher, once["id"], registration="ask")
    rid = (await ask(client, h, once["id"], None)).json()["id"]
    await decide(client, teacher, rid, "approve")
    await buy(client, h, once["id"], None, amount=150000)


async def test_access_given_by_staff_answers_the_request(client: AsyncClient, teacher: Headers,  # noqa: F811
                                                         new_student: NewStudent) -> None:  # noqa: F811
    cid, month, _ = await ask_class(client, teacher)
    h = await new_student()
    await ask(client, h, cid, month)
    assert (await give(client, teacher, cid, month, await member_id(client, h))).status_code == 201
    assert await inbox(client, teacher) == []


# --- the notify list --------------------------------------------------------------------------------------

async def test_notify_me(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    url = f"{L}/classes/{cid}/seat-wait"
    h = await new_student()
    assert error_code(await client.put(url, headers=h)) == "WAIT_NOT_NEEDED"        # they can join
    paying = await new_student()
    out = (await checkout(client, paying, cid, month)).json()
    for _ in range(2):
        assert (await client.put(url, headers=h)).status_code == 204
    assert (await view(client, h, cid))["waiting_for_seat"] is True
    assert (await seats(client, teacher, cid, month))["waiting"] == 1
    (w,) = (await client.get(f"{L}/seat-waits", headers=h)).json()
    assert w["class_id"] == cid and w["available"] is False and w["org"]["slug"]
    # The seat opens.
    await notify(client, payment_key(out), "failed")
    (w,) = (await client.get(f"{L}/seat-waits", headers=h)).json()
    assert w["available"] is True and w["needs_request"] is False
    await settings(client, teacher, cid, registration="ask")
    (w,) = (await client.get(f"{L}/seat-waits", headers=h)).json()
    assert w["available"] is True and w["needs_request"] is True
    await settings(client, teacher, cid, registration="closed")
    (w,) = (await client.get(f"{L}/seat-waits", headers=h)).json()
    assert w["available"] is False
    # Closed registration can be waited for too. Getting a seat takes them off the list.
    other = await new_student()
    assert (await client.put(url, headers=other)).status_code == 204
    assert (await client.delete(url, headers=other)).status_code == 204
    await settings(client, teacher, cid, registration="open")
    await buy(client, h, cid, month)
    assert (await client.get(f"{L}/seat-waits", headers=h)).json() == []
    assert (await seats(client, teacher, cid, month))["waiting"] == 0
    assert error_code(await client.put(url, headers=h)) == "WAIT_NOT_NEEDED"         # they're in
    assert (await client.put(url)).status_code == 401


# --- what students see ---------------------------------------------------------------------------------------

async def test_the_students_view(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=2)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    h = await new_student()
    seat = await month_seat(client, h, cid)
    assert (seat["limit"], seat["left"], seat["full"], seat["problem"]) == (2, 2, False, None)
    assert await month_seat(client, h, cid, "2026-10-01") is None and await month_seat(client, h, cid, "2026-12-01") is None
    await checkout(client, h, cid, month)
    seat = await month_seat(client, h, cid)
    assert seat["paying_until"] and seat["left"] == 1 and seat["problem"] is None
    await buy(client, await new_student(), cid, month)
    other = await month_seat(client, await new_student(), cid)
    assert (other["left"], other["full"], other["problem"], other["paying_until"]) == (0, True, "CLASS_FULL", None)
    assert (await month_seat(client, h, cid))["problem"] is None                  # their own hold
    # The teacher hides the numbers: only full or not.
    await settings(client, teacher, cid, show_seat_count=False)
    other = await month_seat(client, await new_student(), cid)
    assert (other["limit"], other["left"], other["full"]) == (None, None, True)
    # Without a limit nothing is said.
    await settings(client, teacher, cid, seat_limit=None, show_seat_count=True)
    other = await month_seat(client, await new_student(), cid)
    assert (other["limit"], other["left"], other["full"], other["registration"]) == (None, None, False, "open")


async def test_today_says_what_can_be_paid(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, month, slug = k["class"]["id"], k["months"]["open"]["id"], k["class"]["slug"]
    old, follower = await new_student(), await new_student()
    await buy(client, old, cid, month)
    await client.post(f"/api/v1/student/classes/{slug}/enroll", headers=follower)
    (row,) = (await client.get(f"{L}/today", headers=follower)).json()["to_pay"]
    assert row["seat"]["problem"] == "CLASS_FULL"
    december = await open_december(client, teacher, k)
    (row,) = (await client.get(f"{L}/today", headers=old)).json()["to_pay"]
    assert row["month_id"] == december and row["seat"]["problem"] is None and row["seat"]["kept_until"]


# --- the public side ------------------------------------------------------------------------------------------

async def card(client: AsyncClient, class_id: str) -> dict[str, Any]:
    return (await client.get(f"{M}/classes/by-id/{class_id}")).json()


async def test_public_seats(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    k = await published(client, teacher, title="Seated physics", seat_limit=2)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    c = await card(client, cid)
    assert (c["seat_limit"], c["seats_left"], c["is_full"], c["registration"], c["students"]) == (2, 2, False, "open", 0)

    async def listed(**params: Any) -> list[str]:
        found = (await client.get(f"{M}/classes", params={"q": "seated physics", **params})).json()
        assert found["total"] == len(found["items"])
        return [x["id"] for x in found["items"] if x["id"] == cid]

    # Joining without paying isn't a student of a limited class; a payment running now takes a seat.
    await client.post(f"/api/v1/student/classes/{k['class']['slug']}/enroll", headers=await new_student())
    out = (await checkout(client, await new_student(), cid, month)).json()
    assert (await card(client, cid))["seats_left"] == 1 and (await card(client, cid))["students"] == 1
    await notify(client, payment_key(out))
    assert await listed(seats="available") == [cid]
    await buy(client, await new_student(), cid, month)
    c = await card(client, cid)
    assert (c["seats_left"], c["is_full"], c["students"]) == (0, True, 2)
    assert await listed() == [cid] and await listed(seats="available") == []
    page = (await client.get(f"{M}/classes{c['path']}")).json()
    by_month = {m["month_start"]: m for m in page["months"]}
    assert page["class"]["is_full"] is True
    assert by_month["2026-11-01"]["is_full"] is True and by_month["2026-11-01"]["seats_left"] == 0
    assert by_month["2026-12-01"]["is_full"] is False and by_month["2026-12-01"]["seats_left"] is None
    # Lowered below the seats taken: never negative.
    await settings(client, teacher, cid, seat_limit=1)
    assert (await card(client, cid))["seats_left"] == 0
    # Registration.
    await settings(client, teacher, cid, seat_limit=5, registration="ask")
    assert (await card(client, cid))["registration"] == "ask" and await listed(seats="available") == [cid]
    await settings(client, teacher, cid, registration="closed")
    assert await listed(seats="available") == []
    await settings(client, teacher, cid, registration="open", starts_on=(date.today() - timedelta(days=2)).isoformat(),
                   registration_after_start="closed")
    assert (await card(client, cid))["registration"] == "closed"
    # No open month: nothing to join.
    await patch_month(client, teacher, month, status="closed")
    c = await card(client, cid)
    assert (c["registration"], c["seat_limit"], c["is_full"]) == (None, None, False)
    assert await listed(seats="available") == []


async def test_without_a_limit_no_seat_numbers_show_publicly(client: AsyncClient, teacher: Headers,  # noqa: F811
                                                             new_student: NewStudent) -> None:  # noqa: F811
    k = await published(client, teacher)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    await buy(client, await new_student(), cid, month)
    c = await card(client, cid)
    assert (c["seat_limit"], c["seats_left"], c["is_full"], c["registration"]) == (None, None, False, "open")
    assert c["students"] == 1
    months = (await client.get(f"{M}/classes{c['path']}")).json()["months"]
    assert all(m["seats_left"] is None and m["is_full"] is False for m in months)


async def test_kept_and_accepted_seats_show_publicly(client: AsyncClient, teacher: Headers,  # noqa: F811
                                                     new_student: NewStudent) -> None:  # noqa: F811
    k = await published(client, teacher, seat_limit=3)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    await buy(client, await new_student(), cid, month)
    await patch_month(client, teacher, month, status="closed")
    await open_december(client, teacher, k)
    assert (await card(client, cid))["seats_left"] == 2
    await settings(client, teacher, cid, registration="ask")
    h = await new_student()
    rid = (await ask(client, h, cid, k["months"]["upcoming"]["id"])).json()["id"]
    assert (await card(client, cid))["seats_left"] == 2
    await decide(client, teacher, rid, "approve")
    assert (await card(client, cid))["seats_left"] == 1


async def test_hidden_numbers_never_show(client: AsyncClient, seed: Seed, teacher: Headers,  # noqa: F811
                                         new_student: NewStudent) -> None:  # noqa: F811
    k = await published(client, teacher, title="Quiet physics", seat_limit=4321, show_seat_count=False)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    await buy(client, await new_student(), cid, month)
    c = await card(client, cid)
    assert (c["seat_limit"], c["seats_left"], c["is_full"], c["students"]) == (None, None, False, 0)
    numbers: set[int] = set()

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for v in value.values():
                collect(v)
        elif isinstance(value, list):
            for v in value:
                collect(v)
        elif isinstance(value, int):
            numbers.add(value)

    for url in (f"{M}/classes?q=quiet", f"{M}/home", f"{M}/subjects/physics", f"{M}/teachers/{c['teacher_slug']}", f"{M}/classes{c['path']}",
                f"{M}/instructors/{c['teacher_slug']}", f"/api/v1/public/classes/{k['class']['slug']}"):
        r = await client.get(url, headers={"host": seed.a.host})
        assert r.status_code == 200, (url, r.text)
        collect(r.json())
    assert len(numbers) > 3 and not numbers & {4321, 4320}
    async with AppSession() as s:
        row = (await s.execute(text("SELECT * FROM public_seats WHERE class_id = :c"), {"c": cid})).one()
    assert row.seat_limit is None and row.seats_left is None
    await settings(client, teacher, cid, seat_limit=1)
    c = await card(client, cid)
    assert c["is_full"] is True and c["seats_left"] is None
    view_ = await month_seat(client, await new_student(), cid)
    assert view_["full"] is True and view_["left"] is None


async def test_the_public_view_shows_only_public_fields(client: AsyncClient, seed: Seed, teacher: Headers,  # noqa: F811
                                                        new_student: NewStudent) -> None:  # noqa: F811
    k = await published(client, teacher, seat_limit=3)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    await buy(client, await new_student(), cid, month)
    taken = text("SELECT public_seats_taken(:c, :m)")
    async with AppSession() as s:
        rows = (await s.execute(text("SELECT * FROM public_seats WHERE class_id = :c"), {"c": cid})).all()
        assert len(rows) == 1 and set(rows[0]._mapping) == {
            "class_id", "class_month_id", "registration", "seat_limit", "seats_left", "is_full"}
        # Counting for the public never reaches a class the public can't see, or anyone's rows.
        assert (await s.execute(text("SELECT count(*) FROM seat_requests"))).scalar_one() == 0
        assert (await s.execute(text("SELECT count(*) FROM seat_holders(:c, :m)"), {"c": cid, "m": month})).scalar_one() == 0
        assert (await s.execute(taken, {"c": cid, "m": month})).scalar_one() == 1
    async with AdminSession() as a, a.begin():
        await a.execute(text("UPDATE tenants SET is_listed = false WHERE id = :t"), {"t": seed.a.id})
    async with AppSession() as s:
        assert (await s.execute(text("SELECT count(*) FROM public_seats WHERE class_id = :c"), {"c": cid})).scalar_one() == 0
        assert (await s.execute(taken, {"c": cid, "m": month})).scalar_one() == 0
    async with AdminSession() as a, a.begin():
        await a.execute(text("UPDATE tenants SET is_listed = true WHERE id = :t"), {"t": seed.a.id})
    await settings(client, teacher, cid, status="archived")
    async with AppSession() as s:
        assert (await s.execute(taken, {"c": cid, "m": month})).scalar_one() == 0


async def test_guest_cart(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    k = await published(client, teacher, seat_limit=1)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]

    async def problem() -> Any:
        r = await client.post(f"{M}/cart/preview", json={"items": [{"class_id": cid, "class_month_id": month}]})
        assert r.status_code == 200, r.text
        return r.json()["items"][0]["problem"]

    assert await problem() is None
    for registration, code in (("ask", "SEAT_REQUEST_REQUIRED"), ("closed", "REGISTRATION_CLOSED")):
        await settings(client, teacher, cid, registration=registration)
        assert await problem() == code
    await settings(client, teacher, cid, registration="open")
    await buy(client, await new_student(), cid, month)
    assert await problem() == "CLASS_FULL"


async def test_cart_follows_a_request(client: AsyncClient, sms: FakeSms, teacher: Headers,  # noqa: F811
                                      phones: Callable[[], str]) -> None:
    k = await published(client, teacher, registration="ask")
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    h = await main_login(client, sms, phones())
    assert error_code(await add(client, h, cid, month)) == "SEAT_REQUEST_REQUIRED"
    rid = (await ask(client, h, cid, month)).json()["id"]          # asking makes them a member here
    await decide(client, teacher, rid, "approve")
    assert (await add(client, h, cid, month)).status_code == 201
    assert (await client.get("/api/v1/me/cart", headers=h)).json()["ready"] is True
    await expire_requests(cid)
    assert (await client.get("/api/v1/me/cart", headers=h)).json()["items"][0]["problem"] == "SEAT_REQUEST_REQUIRED"


# --- isolation ------------------------------------------------------------------------------------------------

async def test_requests_and_waits_are_isolated(client: AsyncClient, sms: FakeSms, seed: Seed, teacher: Headers,  # noqa: F811
                                               phones: Callable[[], str]) -> None:
    cid, month, _ = await ask_class(client, teacher)
    full = await monthly_class(client, teacher, title="Full", seat_limit=1, registration="closed")
    phone, other_phone = phones(), phones()
    h, other = await main_login(client, sms, phone), await main_login(client, sms, other_phone)
    rid = (await ask(client, h, cid, month)).json()["id"]
    assert (await client.put(f"{L}/classes/{full['class']['id']}/seat-wait", headers=h)).status_code == 204
    # Another student sees and can do nothing with them.
    assert (await client.get(f"{L}/seat-requests", headers=other)).json() == []
    assert (await client.get(f"{L}/seat-waits", headers=other)).json() == []
    assert (await client.delete(f"{L}/classes/{cid}/seat-request", headers=other,
                                params={"class_month_id": month})).status_code == 404
    await client.delete(f"{L}/classes/{full['class']['id']}/seat-wait", headers=other)
    assert len((await client.get(f"{L}/seat-waits", headers=h)).json()) == 1

    for user_phone, count in ((phone, 1), (other_phone, 0)):
        async with user_transaction(await user_id_of(user_phone)) as s:
            for table in ("seat_requests", "seat_waits"):
                assert (await s.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == count
    async with user_transaction(await user_id_of(phone)) as s:                    # the user policy only reads
        assert (await s.execute(text("UPDATE seat_requests SET status = 'approved', held_until = now()"))).rowcount == 0  # type: ignore[attr-defined]
        assert (await s.execute(text("DELETE FROM seat_waits"))).rowcount == 0  # type: ignore[attr-defined]
    async with tenant_transaction(seed.b.id) as s:
        for table in ("seat_requests", "seat_waits"):
            assert (await s.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one() == 0
        assert (await s.execute(text("UPDATE seat_requests SET status = 'withdrawn'"))).rowcount == 0  # type: ignore[attr-defined]
        assert (await s.execute(text("SELECT count(*) FROM seat_holders(:c, :m)"), {"c": cid, "m": month})).scalar_one() == 0
    for table, columns in (("seat_requests", "class_id, student_member_id"), ("seat_waits", "class_id, student_member_id")):
        with pytest.raises(DBAPIError):                      # another tenant's class under its own tenant id
            async with tenant_transaction(seed.b.id) as s:
                await s.execute(text(f"INSERT INTO {table} (tenant_id, {columns}) VALUES (current_tenant_id(), :c, :m)"),
                                {"c": UUID(cid), "m": seed.b.member_id})
    assert (await client.get(f"{L}/seat-requests", headers=h)).json()[0]["id"] == rid


def test_settings_defaults() -> None:
    assert get_settings().seat_request_hold_hours == 48
