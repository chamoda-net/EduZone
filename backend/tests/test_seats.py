"""Seats and registration, step S1 (docs/SEATS.md): counting, holds in both payment paths, the last seat, late payments,
registration, free classes, staff access, the settings switch and what a teacher may see."""

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from datetime import date, timedelta
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from app.modules.seats import service as seats_service
from tests.conftest import AddMember, FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_cart import add, one_time_class, pay
from tests.test_checkout import checkout, fake, ledger, notify, payment_key
from tests.test_learn import main_login
from tests.test_learning import member_id, monthly_class
from tests.test_market import published

Headers = dict[str, str]
NewStudent = Callable[[], Awaitable[Headers]]


@pytest.fixture(autouse=True)
def seats_on(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(get_settings(), "seats_enabled", True)
    yield


@pytest.fixture
async def teacher(client: AsyncClient, sms: FakeSms, seed: Seed) -> Headers:
    return await auth_headers(client, sms, seed.a, seed.a.teacher_phone)


@pytest.fixture
def new_student(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember) -> NewStudent:
    async def make() -> Headers:
        return await auth_headers(client, sms, seed.a, await members(seed.a, "student"))

    return make


@pytest.fixture
def slow_check(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pause between finding a free seat and taking it, so a missing lock always shows."""
    real = seats_service.check

    async def check(*args: Any) -> None:
        await real(*args)
        await asyncio.sleep(0.2)

    monkeypatch.setattr(seats_service, "check", check)


async def seats(client: AsyncClient, teacher: Headers, class_id: str, month_id: str | None = None) -> dict[str, Any]:
    r = await client.get(f"/api/v1/org/classes/{class_id}/seats", headers=teacher,
                         params={"month_id": month_id} if month_id else {})
    assert r.status_code == 200, r.text
    return r.json()


async def settings(client: AsyncClient, teacher: Headers, class_id: str, **values: Any) -> Any:
    return await client.patch(f"/api/v1/org/classes/{class_id}", headers=teacher, json=values)


async def buy(client: AsyncClient, h: Headers, class_id: str, month_id: str | None, amount: int = 200000) -> None:
    out = await checkout(client, h, class_id, month_id)
    assert out.status_code == 201, out.text
    assert (await notify(client, payment_key(out.json()), amount=amount)).json()["outcome"] == "paid"


async def end_holds(class_id: str) -> None:
    """As if the hold's time had passed."""
    async with AdminSession() as s, s.begin():
        await s.execute(text("""
            UPDATE orders SET seat_held_until = seat_held_until - interval '1 hour'
            WHERE id IN (SELECT order_id FROM order_items WHERE class_id = :c)
        """), {"c": class_id})


async def give(client: AsyncClient, teacher: Headers, class_id: str, month_id: str | None, member: str,
               **extra: Any) -> Any:
    return await client.post(f"/api/v1/org/classes/{class_id}/grants", headers=teacher, json={
        "student_member_id": member, "class_month_id": month_id, **extra})


# --- counting ---------------------------------------------------------------------------------------

async def test_paid_seats_fill_the_class(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=2)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    for _ in range(2):
        await buy(client, await new_student(), cid, month)
    s = await seats(client, teacher, cid, month)
    assert (s["limit"], s["taken"], s["free"], s["over_by"]) == (2, 2, 0, 0)
    assert {x["kind"] for x in s["seats"]} == {"access"} and {x["source"] for x in s["seats"]} == {"purchase"}
    third = await new_student()
    assert error_code(await checkout(client, third, cid, month)) == "CLASS_FULL"
    # More seats: the third gets in. Fewer seats: nobody leaves and the class is full.
    assert (await settings(client, teacher, cid, seat_limit=3)).status_code == 200
    await buy(client, third, cid, month)
    assert (await settings(client, teacher, cid, seat_limit=1)).status_code == 200
    s = await seats(client, teacher, cid, month)
    assert (s["taken"], s["free"], s["over_by"]) == (3, 0, 2)
    assert error_code(await checkout(client, await new_student(), cid, month)) == "CLASS_FULL"
    # No limit again.
    assert (await settings(client, teacher, cid, seat_limit=None)).status_code == 200
    s = await seats(client, teacher, cid, month)
    assert (s["limit"], s["free"], s["over_by"]) == (None, None, 0)
    assert (await checkout(client, await new_student(), cid, month)).status_code == 201


async def test_joining_without_paying_takes_no_seat(client: AsyncClient, teacher: Headers,
                                                    new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    for _ in range(3):
        h = await new_student()
        assert (await client.post(f"/api/v1/student/classes/{k['class']['slug']}/enroll", headers=h)).status_code == 200
    assert (await seats(client, teacher, cid, month))["taken"] == 0
    await buy(client, await new_student(), cid, month)


async def test_paying_joins_the_class_only_when_it_succeeds(client: AsyncClient, teacher: Headers,
                                                            new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher)
    slug, cid, month = k["class"]["slug"], k["class"]["id"], k["months"]["open"]["id"]
    h = await new_student()
    out = (await checkout(client, h, cid, month)).json()
    assert (await client.get(f"/api/v1/student/classes/{slug}", headers=h)).json()["enrolled"] is False
    await notify(client, payment_key(out))
    assert (await client.get(f"/api/v1/student/classes/{slug}", headers=h)).json()["enrolled"] is True


async def test_limits_are_per_month(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=1)
    cid = k["class"]["id"]
    await buy(client, await new_student(), cid, k["months"]["open"]["id"])
    await client.patch(f"/api/v1/org/months/{k['months']['upcoming']['id']}", headers=teacher, json={"status": "open"})
    december = k["months"]["upcoming"]["id"]
    assert (await seats(client, teacher, cid, december))["taken"] == 1           # November's student, kept (S2)
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE class_months SET renew_until = now() WHERE id = :m"), {"m": december})
    assert (await seats(client, teacher, cid, december))["taken"] == 0
    await buy(client, await new_student(), cid, december)


async def test_one_time_class(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:
    c = await one_time_class(client, teacher)
    assert (await settings(client, teacher, c["id"], seat_limit=1)).status_code == 200
    await buy(client, await new_student(), c["id"], None, amount=150000)
    assert (await seats(client, teacher, c["id"]))["taken"] == 1
    assert error_code(await checkout(client, await new_student(), c["id"])) == "CLASS_FULL"


# --- holds --------------------------------------------------------------------------------------------

async def test_a_hold_blocks_others_until_it_ends(client: AsyncClient, teacher: Headers,
                                                  new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    first, second = await new_student(), await new_student()
    out = (await checkout(client, first, cid, month)).json()
    s = await seats(client, teacher, cid, month)
    assert s["taken"] == 1 and s["seats"][0]["kind"] == "paying" and s["seats"][0]["held_until"]
    assert error_code(await checkout(client, second, cid, month)) == "CLASS_FULL"

    # Starting again reuses the hold: same end, still one seat.
    again = await checkout(client, first, cid, month)
    assert again.status_code == 201
    after = await seats(client, teacher, cid, month)
    assert after["taken"] == 1 and after["seats"][0]["held_until"] == s["seats"][0]["held_until"]

    # Both payments end without success: the seat is free at once.
    await notify(client, payment_key(out), "failed")
    assert (await seats(client, teacher, cid, month))["taken"] == 1          # the second attempt still runs
    await notify(client, payment_key(again.json()), "cancelled")
    assert (await seats(client, teacher, cid, month))["taken"] == 0

    # Or its time passes.
    assert (await checkout(client, second, cid, month)).status_code == 201
    await end_holds(cid)
    assert (await seats(client, teacher, cid, month))["taken"] == 0
    assert (await checkout(client, first, cid, month)).status_code == 201


async def test_only_a_few_unfinished_holds_a_day(client: AsyncClient, teacher: Headers,
                                                 new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=5)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    h = await new_student()
    # Declined cards don't count.
    for _ in range(4):
        out = await checkout(client, h, cid, month)
        assert out.status_code == 201
        await notify(client, payment_key(out.json()), "failed")
    for _ in range(get_settings().seat_holds_per_day):
        assert (await checkout(client, h, cid, month)).status_code == 201
        assert (await checkout(client, h, cid, month)).status_code == 201     # reused, not counted again
        await end_holds(cid)
    assert error_code(await checkout(client, h, cid, month)) == "SEAT_HOLD_LIMIT"
    # Only where seats are limited.
    await settings(client, teacher, cid, seat_limit=None)
    assert (await checkout(client, h, cid, month)).status_code == 201


async def test_the_last_seat_goes_to_one_student(client: AsyncClient, teacher: Headers, new_student: NewStudent,
                                                 slow_check: None) -> None:
    """Everyone presses Pay at the same moment, several times over: one hold each time."""
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    students = [await new_student() for _ in range(5)]
    for _ in range(3):
        results = await asyncio.gather(*(checkout(client, h, cid, month) for h in students))
        assert sorted(r.status_code for r in results) == [201, 409, 409, 409, 409]
        assert {error_code(r) for r in results if r.status_code == 409} == {"CLASS_FULL"}
        winner = next(r for r in results if r.status_code == 201)
        await notify(client, payment_key(winner.json()), "failed")


async def test_the_last_seat_through_the_cart(client: AsyncClient, sms: FakeSms, teacher: Headers,
                                              phones: Callable[[], str], slow_check: None) -> None:
    k = await published(client, teacher, seat_limit=1)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    students = [await main_login(client, sms, phones()) for _ in range(4)]
    for h in students:
        assert (await add(client, h, cid, month)).status_code == 201            # the cart holds nothing
    assert (await seats(client, teacher, cid, month))["taken"] == 0
    results = await asyncio.gather(*(client.post("/api/v1/me/checkouts", headers=h) for h in students))
    assert sorted(r.status_code for r in results) == [201, 409, 409, 409]
    assert {error_code(r) for r in results if r.status_code == 409} == {"CART_HAS_PROBLEMS"}
    # Everyone else's cart now says why.
    losers = [h for h, r in zip(students, results, strict=True) if r.status_code == 409]
    cart = (await client.get("/api/v1/me/cart", headers=losers[0])).json()
    assert cart["items"][0]["problem"] == "CLASS_FULL" and cart["ready"] is False
    winner = next(r for r in results if r.status_code == 201).json()
    form = fake().notification(payment_key(winner), "succeeded", 200000, "LKR")
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "paid"
    assert (await seats(client, teacher, cid, month))["seats"][0]["kind"] == "access"


async def test_a_cart_that_fails_halfway_frees_its_seats(
    client: AsyncClient, sms: FakeSms, seed: Seed, teacher: Headers, phones: Callable[[], str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.modules.checkout import service as checkout_service

    k = await published(client, teacher, seat_limit=1)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    teacher_b = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    other = await one_time_class(client, teacher_b)
    h = await main_login(client, sms, phones())
    assert (await add(client, h, cid, month)).status_code == 201
    assert (await add(client, h, other["id"])).status_code == 201

    real = checkout_service.create_order
    calls = 0

    async def second_fails(*args: Any, **kwargs: Any) -> UUID:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("the database went away")
        return await real(*args, **kwargs)

    monkeypatch.setattr(checkout_service, "create_order", second_fails)
    with pytest.raises(RuntimeError):
        await client.post("/api/v1/me/checkouts", headers=h)
    monkeypatch.setattr(checkout_service, "create_order", real)

    assert calls == 2
    async with AdminSession() as s:
        statuses = (await s.execute(text("""
            SELECT o.status, p.status AS payment FROM orders o JOIN payments p ON p.order_id = o.id
            WHERE o.tenant_id IN (:a, :b)
        """), {"a": seed.a.id, "b": seed.b.id})).all()
    assert [(r.status, r.payment) for r in statuses] == [("failed", "failed")]
    assert (await seats(client, teacher, cid, month))["taken"] == 0
    # And the same cart can be paid afterwards.
    out, form = await pay(client, h, amount=350000)
    assert (await client.post("/api/v1/webhooks/fake", data=form)).json()["outcome"] == "paid"


async def test_a_late_payment_keeps_the_student(client: AsyncClient, seed: Seed, teacher: Headers,
                                                new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    slow, quick = await new_student(), await new_student()
    out = (await checkout(client, slow, cid, month)).json()
    await end_holds(cid)
    await buy(client, quick, cid, month)
    for outcome in ("paid", "duplicate"):                           # and the notification again: nothing changes
        assert (await notify(client, payment_key(out))).json()["outcome"] == outcome
        s = await seats(client, teacher, cid, month)
        assert (s["taken"], s["free"], s["over_by"]) == (2, 0, 1)
    assert (await ledger(seed.a.id))["sales"] == 2 and (await ledger(seed.a.id))["unbalanced"] == 0
    async with AdminSession() as s:
        audits = (await s.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'seat.over_limit' AND "
                                       "entity_id = :c"), {"c": cid})).scalar_one()
    assert audits == 1


async def test_a_late_payment_with_a_free_seat_is_ordinary(client: AsyncClient, teacher: Headers,
                                                           new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    out = (await checkout(client, await new_student(), cid, month)).json()
    await end_holds(cid)
    assert (await notify(client, payment_key(out))).json()["outcome"] == "paid"
    assert (await seats(client, teacher, cid, month))["over_by"] == 0
    async with AdminSession() as s:
        assert (await s.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'seat.over_limit' AND "
                                     "entity_id = :c"), {"c": cid})).scalar_one() == 0


# --- registration ---------------------------------------------------------------------------------------

async def test_registration(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=5)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    old = await new_student()
    await buy(client, old, cid, month)
    paying = await new_student()
    started = (await checkout(client, paying, cid, month)).json()

    assert (await settings(client, teacher, cid, registration="ask")).status_code == 200
    assert error_code(await checkout(client, await new_student(), cid, month)) == "SEAT_REQUEST_REQUIRED"
    assert (await settings(client, teacher, cid, registration="closed")).status_code == 200
    fresh = await new_student()
    assert error_code(await checkout(client, fresh, cid, month)) == "REGISTRATION_CLOSED"
    # Someone already paying may finish, and a student of this month continues next month.
    assert (await checkout(client, paying, cid, month)).status_code == 201
    assert (await notify(client, payment_key(started))).json()["outcome"] == "paid"
    december = k["months"]["upcoming"]["id"]
    await client.patch(f"/api/v1/org/months/{december}", headers=teacher, json={"status": "open"})
    assert error_code(await checkout(client, fresh, cid, december)) == "REGISTRATION_CLOSED"
    await buy(client, old, cid, december)
    # Leaving the class makes them new again.
    slug = k["class"]["slug"]
    assert (await client.delete(f"/api/v1/student/classes/{slug}/enroll", headers=paying)).status_code == 204
    assert error_code(await checkout(client, paying, cid, december)) == "REGISTRATION_CLOSED"
    # Registration works without a seat limit too, and a full class says full first.
    await settings(client, teacher, cid, seat_limit=None)
    assert error_code(await checkout(client, fresh, cid, month)) == "REGISTRATION_CLOSED"
    await settings(client, teacher, cid, seat_limit=1)
    assert error_code(await checkout(client, fresh, cid, month)) == "CLASS_FULL"


async def test_registration_switches_on_the_start_date(client: AsyncClient, teacher: Headers,
                                                       new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    bad = await settings(client, teacher, cid, registration_after_start="closed")
    assert bad.status_code == 422 and error_code(bad) == "SEATS_INVALID"
    future, past = (date.today() + timedelta(days=5)).isoformat(), (date.today() - timedelta(days=2)).isoformat()
    ok = await settings(client, teacher, cid, starts_on=future, registration_after_start="closed")
    assert ok.status_code == 200 and ok.json()["starts_on"] == future
    assert (await seats(client, teacher, cid, month))["registration"] == "open"
    assert (await checkout(client, await new_student(), cid, month)).status_code == 201
    await settings(client, teacher, cid, starts_on=past)
    assert (await seats(client, teacher, cid, month))["registration"] == "closed"
    assert error_code(await checkout(client, await new_student(), cid, month)) == "REGISTRATION_CLOSED"
    # The date can't go while a switch depends on it.
    assert error_code(await settings(client, teacher, cid, starts_on=None)) == "SEATS_INVALID"


async def test_past_months_need_no_seat(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=1, registration="closed")
    cid, past, month = k["class"]["id"], k["months"]["closed"]["id"], k["months"]["open"]["id"]
    h = await new_student()
    await client.post(f"/api/v1/student/classes/{k['class']['slug']}/enroll", headers=h)
    req = (await client.post(f"/api/v1/student/months/{past}/late-request", headers=h, json={})).json()
    await client.post(f"/api/v1/org/late-requests/{req['id']}/decision", headers=teacher, json={"decision": "approve"})
    await buy(client, h, cid, past)
    assert (await seats(client, teacher, cid, past))["taken"] == 0
    # Having bought last month late doesn't make them a continuing student.
    assert error_code(await checkout(client, h, cid, month)) == "REGISTRATION_CLOSED"


# --- free classes ---------------------------------------------------------------------------------------

async def test_free_class(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:
    c = (await client.post("/api/v1/org/classes", headers=teacher, json={
        "title": "Free revision", "pricing_model": "free", "seat_limit": 1})).json()
    await settings(client, teacher, c["id"], status="published")
    url = f"/api/v1/student/classes/{c['slug']}/enroll"
    first, second = await new_student(), await new_student()
    for _ in range(2):                                                       # joining twice is fine
        assert (await client.post(url, headers=first)).json()["has_class_access"] is True
    assert error_code(await client.post(url, headers=second)) == "CLASS_FULL"
    assert (await client.get(f"/api/v1/student/classes/{c['slug']}", headers=second)).json()["enrolled"] is False
    # Leaving ends the access and frees the seat; coming back needs a seat.
    assert (await client.delete(url, headers=first)).status_code == 204
    assert (await client.get(f"/api/v1/student/classes/{c['slug']}", headers=first)).json()["has_class_access"] is False
    assert (await client.post(url, headers=second)).status_code == 200
    assert error_code(await client.post(url, headers=first)) == "CLASS_FULL"
    await settings(client, teacher, c["id"], seat_limit=None, registration="closed")
    assert error_code(await client.post(url, headers=first)) == "REGISTRATION_CLOSED"


async def test_the_last_free_seat(client: AsyncClient, teacher: Headers, new_student: NewStudent,
                                  slow_check: None) -> None:
    c = (await client.post("/api/v1/org/classes", headers=teacher, json={
        "title": "Free revision", "pricing_model": "free", "seat_limit": 1})).json()
    await settings(client, teacher, c["id"], status="published")
    students = [await new_student() for _ in range(4)]
    url = f"/api/v1/student/classes/{c['slug']}/enroll"
    results = await asyncio.gather(*(client.post(url, headers=h) for h in students))
    assert sorted(r.status_code for r in results) == [200, 409, 409, 409]


async def test_someone_who_left_before_keeps_no_seat(client: AsyncClient, seed: Seed, teacher: Headers,
                                                     new_student: NewStudent) -> None:
    """Before this step leaving a free class kept its access: such a student takes no seat."""
    c = (await client.post("/api/v1/org/classes", headers=teacher, json={
        "title": "Free revision", "pricing_model": "free", "seat_limit": 1})).json()
    await settings(client, teacher, c["id"], status="published")
    url = f"/api/v1/student/classes/{c['slug']}/enroll"
    left = await new_student()
    await client.post(url, headers=left)
    async with tenant_transaction(seed.a.id) as s:
        await s.execute(text("UPDATE class_enrollments SET status = 'left' WHERE class_id = :c"), {"c": c["id"]})
    assert (await client.post(url, headers=await new_student())).status_code == 200
    assert error_code(await client.post(url, headers=left)) == "CLASS_FULL"


# --- staff ----------------------------------------------------------------------------------------------

async def test_staff_may_go_over_on_purpose(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=1, registration="closed")
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    a, b = [await member_id(client, await new_student()) for _ in range(2)]
    first = await give(client, teacher, cid, month, a, source="scholarship")     # registration is for students
    assert first.status_code == 201, first.text
    assert error_code(await give(client, teacher, cid, month, b)) == "CLASS_FULL"
    assert (await give(client, teacher, cid, month, b, allow_over_limit=True)).status_code == 201
    s = await seats(client, teacher, cid, month)
    assert s["over_by"] == 1 and {x["source"] for x in s["seats"]} == {"scholarship", "manual"}
    # Taking access back frees the seat. A past month takes none.
    assert (await client.post(f"/api/v1/org/grants/{first.json()['id']}/revoke", headers=teacher,
                              json={})).status_code == 204
    assert (await seats(client, teacher, cid, month))["over_by"] == 0
    for m in (a, b):
        assert (await give(client, teacher, cid, k["months"]["closed"]["id"], m)).status_code == 201
    assert (await seats(client, teacher, cid, k["months"]["closed"]["id"]))["taken"] == 0


async def test_turning_a_limit_on_for_a_running_class(client: AsyncClient, teacher: Headers,
                                                      new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    for _ in range(2):
        await buy(client, await new_student(), cid, month)
    paying = await new_student()
    out = (await checkout(client, paying, cid, month)).json()
    assert (await settings(client, teacher, cid, seat_limit=3)).status_code == 200
    assert (await seats(client, teacher, cid, month))["taken"] == 3                  # the payment running now counts
    assert error_code(await checkout(client, await new_student(), cid, month)) == "CLASS_FULL"
    await notify(client, payment_key(out))
    assert (await seats(client, teacher, cid, month))["over_by"] == 0


async def test_seat_list_belongs_to_the_classs_staff(client: AsyncClient, sms: FakeSms, seed: Seed, teacher: Headers,
                                                     members: AddMember, new_student: NewStudent) -> None:
    k = await monthly_class(client, teacher, seat_limit=3)
    cid, month = k["class"]["id"], k["months"]["open"]["id"]
    h = await new_student()
    await buy(client, h, cid, month)
    url = f"/api/v1/org/classes/{cid}/seats"
    other_teacher = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    other_org = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    assert (await client.get(url, headers=owner, params={"month_id": month})).json()["taken"] == 1
    for who, status in ((other_teacher, 404), (other_org, 404), (h, 403)):
        assert (await client.get(url, headers=who, params={"month_id": month})).status_code == status
    assert error_code(await client.get(url, headers=teacher)) == "MONTH_REQUIRED"
    other = await monthly_class(client, teacher, title="Other")
    assert error_code(await client.get(url, headers=teacher, params={"month_id": other["months"]["open"]["id"]})) == "MONTH_INVALID"
    assert (await client.patch(f"/api/v1/org/classes/{cid}", headers=other_teacher,
                               json={"seat_limit": 1})).status_code == 404


async def test_settings_validation(client: AsyncClient, teacher: Headers) -> None:
    k = await monthly_class(client, teacher)
    cid = k["class"]["id"]
    for bad in ({"seat_limit": 0}, {"seat_limit": 10_001}, {"registration": "maybe"}, {"registration": None},
                {"show_seat_count": None}):
        assert (await settings(client, teacher, cid, **bad)).status_code == 422
    out = (await settings(client, teacher, cid, seat_limit=10, show_seat_count=False)).json()
    assert (out["seat_limit"], out["show_seat_count"], out["registration"]) == (10, False, "open")


async def test_off_by_default(client: AsyncClient, teacher: Headers, monkeypatch: pytest.MonkeyPatch) -> None:
    k = await monthly_class(client, teacher, seat_limit=5)
    cid = k["class"]["id"]
    monkeypatch.setattr(get_settings(), "seats_enabled", False)
    for values in ({"seat_limit": 6}, {"registration": "closed"}, {"show_seat_count": False}):
        assert error_code(await settings(client, teacher, cid, **values)) == "SEATS_NOT_AVAILABLE"
    refused = await client.post("/api/v1/org/classes", headers=teacher, json={
        "title": "X", "pricing_model": "free", "seat_limit": 5})
    assert error_code(refused) == "SEATS_NOT_AVAILABLE"
    # Everything else still works, and a limit can be taken off.
    assert (await settings(client, teacher, cid, title="New title")).status_code == 200
    assert (await settings(client, teacher, cid, seat_limit=None)).json()["seat_limit"] is None


async def test_courses_have_no_seats(seed: Seed) -> None:
    async with AdminSession() as s:
        with pytest.raises(IntegrityError, match="classes_seats_tuition_only"):
            await s.execute(text("""
                INSERT INTO classes (tenant_id, teacher_member_id, title, slug, kind, pricing_model, seat_limit)
                VALUES (:t, :m, 'Course', 'seat-course', 'course', 'free', 5)
            """), {"t": seed.a.id, "m": seed.a.member_id})
