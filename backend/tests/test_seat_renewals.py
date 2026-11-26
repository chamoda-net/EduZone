"""Seats, step S2 (docs/SEATS.md): returning students keep their seat until the renewal date; opening dates; what counts
as returning; staff keeping and releasing a seat."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from app.modules.seats.settings import renew_until
from tests.conftest import AddMember, FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_checkout import checkout, notify, payment_key
from tests.test_learning import member_id, monthly_class
from tests.test_seats import (  # noqa: F401  (fixtures)
    NewStudent,
    buy,
    give,
    new_student,
    seats,
    seats_on,
    settings,
    teacher,
)

Headers = dict[str, str]


async def patch_month(client: AsyncClient, teacher: Headers, month_id: str, **values: Any) -> Any:
    return await client.patch(f"/api/v1/org/months/{month_id}", headers=teacher, json=values)


async def open_december(client: AsyncClient, teacher: Headers, k: dict[str, Any]) -> str:
    december = k["months"]["upcoming"]["id"]
    assert (await patch_month(client, teacher, december, status="open")).status_code == 200
    return december


async def renewal_passed(month_id: str) -> None:
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE class_months SET renew_until = now() - interval '1 second' WHERE id = :m"),
                        {"m": month_id})


async def decide(client: AsyncClient, teacher: Headers, month_id: str, member: str, action: str, *,
                 hours: float | None = None, **extra: Any) -> Any:
    body: dict[str, Any] = {"action": action, **extra}
    if hours is not None:
        body["keep_until"] = (datetime.now(UTC) + timedelta(hours=hours)).isoformat()
    return await client.put(f"/api/v1/org/months/{month_id}/seat-keeps/{member}", headers=teacher, json=body)


def kinds(s: dict[str, Any]) -> list[str]:
    return [x["kind"] for x in s["seats"]]


# --- the renewal date -------------------------------------------------------------------------------

def test_renewal_date() -> None:
    november = date(2026, 11, 1)
    # The end of the 7th in Sri Lanka is 18:30 UTC, however early the month opens.
    early = datetime(2026, 10, 25, 6, tzinfo=UTC)
    assert renew_until(november, 7, early) == datetime(2026, 11, 7, 18, 30, tzinfo=UTC)
    assert renew_until(november, 28, early) == datetime(2026, 11, 28, 18, 30, tzinfo=UTC)
    # A month that opens late leaves at least three days.
    for late in (datetime(2026, 11, 6, 0, tzinfo=UTC), datetime(2026, 11, 20, 9, tzinfo=UTC)):
        assert renew_until(november, 7, late) == late + timedelta(days=3)
    # The last day of February, across a year end.
    assert renew_until(date(2027, 1, 1), 1, early) == datetime(2027, 1, 1, 18, 30, tzinfo=UTC)


async def test_opening_a_month(client: AsyncClient, teacher: Headers) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=5, renewal_day=10)
    december = k["months"]["upcoming"]
    assert december["opened_at"] is None and december["renew_until"] is None
    assert k["months"]["open"]["opened_at"] and k["months"]["open"]["renew_until"]
    assert error_code(await patch_month(client, teacher, december["id"],
                                        renew_until="2026-12-09T00:00:00Z")) == "MONTH_NOT_OPEN"
    out = (await patch_month(client, teacher, december["id"], status="open")).json()
    assert out["opened_at"]
    expected = renew_until(date(2026, 12, 1), 10, datetime.fromisoformat(out["opened_at"]))
    assert datetime.fromisoformat(out["renew_until"]) == expected
    # Fixed once open: changing the class's day doesn't move it, staff can.
    await settings(client, teacher, k["class"]["id"], renewal_day=3)
    again = (await patch_month(client, teacher, december["id"], fee_cents=100000)).json()
    assert again["renew_until"] == out["renew_until"] and again["opened_at"] == out["opened_at"]
    moved = (await patch_month(client, teacher, december["id"], renew_until="2027-01-05T00:00:00Z")).json()
    assert datetime.fromisoformat(moved["renew_until"]) == datetime(2027, 1, 5, tzinfo=UTC)
    # Closed and opened again keeps its dates; opened by mistake starts over.
    await patch_month(client, teacher, december["id"], status="closed")
    assert (await patch_month(client, teacher, december["id"], status="open")).json()["opened_at"] == out["opened_at"]
    back = (await patch_month(client, teacher, december["id"], status="upcoming")).json()
    assert back["opened_at"] is None and back["renew_until"] is None
    for bad in (0, 29, None):
        assert (await settings(client, teacher, k["class"]["id"], renewal_day=bad)).status_code == 422


# --- keeping a seat -----------------------------------------------------------------------------------

async def test_returning_students_keep_their_seats(client: AsyncClient, teacher: Headers,  # noqa: F811
                                                   new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=2)
    cid, november, slug = k["class"]["id"], k["months"]["open"]["id"], k["class"]["slug"]
    stays, drops, fresh = [await new_student() for _ in range(3)]
    for h in (stays, drops):
        await buy(client, h, cid, november)
    december = await open_december(client, teacher, k)

    s = await seats(client, teacher, cid, december)
    assert (s["taken"], s["free"]) == (2, 0) and kinds(s) == ["kept", "kept"] and s["seats"][0]["held_until"]
    assert error_code(await checkout(client, fresh, cid, december)) == "CLASS_FULL"
    view = (await client.get(f"/api/v1/student/classes/{slug}", headers=stays)).json()
    by_month = {m["month_start"]: (m["seat"] or {}).get("kept_until") for m in view["months"]}
    assert by_month["2026-12-01"] == s["seats"][0]["held_until"] and by_month["2026-11-01"] is None
    fresh_view = (await client.get(f"/api/v1/student/classes/{slug}", headers=fresh)).json()
    assert all((m["seat"] or {}).get("kept_until") is None for m in fresh_view["months"])

    # Renewing works whatever registration says; the seat isn't counted twice while paying or after.
    await settings(client, teacher, cid, registration="closed")
    out = await checkout(client, stays, cid, december)
    assert out.status_code == 201 and kinds(await seats(client, teacher, cid, december)) == ["paying", "kept"]
    await notify(client, payment_key(out.json()))
    s = await seats(client, teacher, cid, december)
    assert s["taken"] == 2 and kinds(s) == ["access", "kept"] and s["lapsed"] == []
    view = (await client.get(f"/api/v1/student/classes/{slug}", headers=stays)).json()
    assert all((m["seat"] or {}).get("kept_until") is None for m in view["months"])             # renewed: nothing left to do

    # After the date the seat is open to new students, if registration is.
    await renewal_passed(december)
    s = await seats(client, teacher, cid, december)
    assert (s["taken"], s["free"]) == (1, 1) and len(s["lapsed"]) == 1 and s["lapsed"][0]["released"] is False
    assert error_code(await checkout(client, fresh, cid, december)) == "REGISTRATION_CLOSED"
    await settings(client, teacher, cid, registration="open")
    await buy(client, fresh, cid, december)
    assert error_code(await checkout(client, drops, cid, december)) == "CLASS_FULL"


async def test_late_returner_takes_a_free_seat(client: AsyncClient, teacher: Headers,  # noqa: F811
                                               new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=1)
    cid = k["class"]["id"]
    h = await new_student()
    await buy(client, h, cid, k["months"]["open"]["id"])
    december = await open_december(client, teacher, k)
    await renewal_passed(december)
    await settings(client, teacher, cid, registration="closed")
    await buy(client, h, cid, december)                  # a free seat, and they aren't new


async def test_kept_until_the_last_moment(client: AsyncClient, teacher: Headers,  # noqa: F811
                                          new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=1)
    cid = k["class"]["id"]
    await buy(client, await new_student(), cid, k["months"]["open"]["id"])
    december = await open_december(client, teacher, k)
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE class_months SET renew_until = now() + interval '30 seconds' WHERE id = :m"),
                        {"m": december})
    assert error_code(await checkout(client, await new_student(), cid, december)) == "CLASS_FULL"
    await renewal_passed(december)
    assert (await checkout(client, await new_student(), cid, december)).status_code == 201


async def test_lowering_the_limit_never_breaks_a_kept_seat(client: AsyncClient, teacher: Headers,  # noqa: F811
                                                           new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=3)
    cid = k["class"]["id"]
    students = [await new_student() for _ in range(3)]
    for h in students:
        await buy(client, h, cid, k["months"]["open"]["id"])
    december = await open_december(client, teacher, k)
    await settings(client, teacher, cid, seat_limit=1)
    for h in students:
        await buy(client, h, cid, december)
    assert (await seats(client, teacher, cid, december))["over_by"] == 2


# --- who is returning -----------------------------------------------------------------------------------

async def test_a_holiday_month_breaks_nothing(client: AsyncClient, teacher: Headers,  # noqa: F811
                                              new_student: NewStudent) -> None:  # noqa: F811
    """November, then no December and January opens: last month is November. A month never opened doesn't count."""
    k = await monthly_class(client, teacher, seat_limit=1)
    cid = k["class"]["id"]
    await buy(client, await new_student(), cid, k["months"]["open"]["id"])
    january = (await client.post(f"/api/v1/org/classes/{cid}/months", headers=teacher,
                                 json={"month_start": "2027-01-01", "status": "open"})).json()
    assert kinds(await seats(client, teacher, cid, january["id"])) == ["kept"]     # December stayed upcoming
    # Once December opens, January's previous month is December, where nobody has a seat yet.
    december = await open_december(client, teacher, k)
    assert kinds(await seats(client, teacher, cid, december)) == ["kept"]
    assert kinds(await seats(client, teacher, cid, january["id"])) == []


async def test_skipping_a_month_makes_a_new_student(client: AsyncClient, teacher: Headers,  # noqa: F811
                                                    new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=5)
    cid = k["class"]["id"]
    h = await new_student()
    await buy(client, h, cid, k["months"]["open"]["id"])
    await open_december(client, teacher, k)
    january = (await client.post(f"/api/v1/org/classes/{cid}/months", headers=teacher,
                                 json={"month_start": "2027-01-01", "status": "open"})).json()
    await settings(client, teacher, cid, registration="closed")
    assert kinds(await seats(client, teacher, cid, january["id"])) == []
    assert error_code(await checkout(client, h, cid, january["id"])) == "REGISTRATION_CLOSED"


async def test_two_open_months_never_promise_more_seats(client: AsyncClient, teacher: Headers,  # noqa: F811
                                                        new_student: NewStudent) -> None:  # noqa: F811
    """December is open and full; someone then joins November: no kept seat in December."""
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, november = k["class"]["id"], k["months"]["open"]["id"]
    december = await open_december(client, teacher, k)
    await buy(client, await new_student(), cid, december)
    late = await new_student()
    await buy(client, late, cid, november)
    s = await seats(client, teacher, cid, december)
    assert (s["taken"], s["over_by"]) == (1, 0) and kinds(s) == ["access"] and len(s["lapsed"]) == 1
    assert error_code(await checkout(client, late, cid, december)) == "CLASS_FULL"
    # With room they need no approval, because they are in the class.
    await settings(client, teacher, cid, seat_limit=2, registration="ask")
    await buy(client, late, cid, december)


async def test_leaving_gives_up_the_kept_seat(client: AsyncClient, teacher: Headers,  # noqa: F811
                                              new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, slug, november = k["class"]["id"], k["class"]["slug"], k["months"]["open"]["id"]
    h = await new_student()
    await buy(client, h, cid, november)
    december = await open_december(client, teacher, k)
    assert (await client.delete(f"/api/v1/student/classes/{slug}/enroll", headers=h)).status_code == 204
    # The paid month is still theirs; next month's seat is free, and rejoining doesn't bring it back.
    assert (await seats(client, teacher, cid, november))["taken"] == 1
    assert (await seats(client, teacher, cid, december))["taken"] == 0
    assert (await client.post(f"/api/v1/student/classes/{slug}/enroll", headers=h)).status_code == 200
    s = await seats(client, teacher, cid, december)
    assert s["taken"] == 0 and len(s["lapsed"]) == 1
    await settings(client, teacher, cid, registration="closed")
    assert error_code(await checkout(client, h, cid, december)) == "REGISTRATION_CLOSED"


@pytest.mark.parametrize("how", ["revoked", "suspended", "removed"])
async def test_no_seat_is_kept_for(client: AsyncClient, seed: Seed, teacher: Headers, new_student: NewStudent,  # noqa: F811
                                   how: str) -> None:
    k = await monthly_class(client, teacher, seat_limit=1)
    cid = k["class"]["id"]
    h = await new_student()
    member = await member_id(client, h)
    grant = (await give(client, teacher, cid, k["months"]["open"]["id"], member)).json()
    december = await open_december(client, teacher, k)
    assert kinds(await seats(client, teacher, cid, december)) == ["kept"]           # a scholarship keeps one too
    if how == "revoked":
        await client.post(f"/api/v1/org/grants/{grant['id']}/revoke", headers=teacher, json={})
    else:
        table, status = (("tenant_members", "suspended") if how == "suspended" else ("class_enrollments", "removed"))
        where = "id = :m" if how == "suspended" else "student_member_id = :m"
        async with tenant_transaction(seed.a.id) as s:
            await s.execute(text(f"UPDATE {table} SET status = :st WHERE {where}"), {"st": status, "m": member})
    assert (await seats(client, teacher, cid, december))["taken"] == 0


async def test_a_month_bought_late_keeps_nothing(client: AsyncClient, teacher: Headers,  # noqa: F811
                                                 new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=1)
    cid, november, slug = k["class"]["id"], k["months"]["open"]["id"], k["class"]["slug"]
    await patch_month(client, teacher, november, status="closed")
    h = await new_student()
    await client.post(f"/api/v1/student/classes/{slug}/enroll", headers=h)
    req = (await client.post(f"/api/v1/student/months/{november}/late-request", headers=h, json={})).json()
    await client.post(f"/api/v1/org/late-requests/{req['id']}/decision", headers=teacher, json={"decision": "approve"})
    await buy(client, h, cid, november)
    december = await open_december(client, teacher, k)
    s = await seats(client, teacher, cid, december)
    assert s["taken"] == 0 and s["lapsed"] == []


async def test_only_open_months_keep_seats(client: AsyncClient, teacher: Headers,  # noqa: F811
                                           new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=1)
    cid = k["class"]["id"]
    await buy(client, await new_student(), cid, k["months"]["open"]["id"])
    december = k["months"]["upcoming"]["id"]
    assert (await seats(client, teacher, cid, december))["taken"] == 0
    await open_december(client, teacher, k)
    await patch_month(client, teacher, december, status="closed")
    assert (await seats(client, teacher, cid, december))["taken"] == 0


# --- staff decisions --------------------------------------------------------------------------------------

async def test_release_and_keep(client: AsyncClient, teacher: Headers,  # noqa: F811
                                new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=1)
    cid = k["class"]["id"]
    old, fresh = await new_student(), await new_student()
    member = await member_id(client, old)
    await buy(client, old, cid, k["months"]["open"]["id"])
    december = await open_december(client, teacher, k)

    s = (await decide(client, teacher, december, member, "release")).json()
    assert s["taken"] == 0 and s["lapsed"][0]["released"] is True
    out = await checkout(client, fresh, cid, december)
    assert out.status_code == 201
    # Someone else is paying now: undoing the release or keeping it would go over, so it must be on purpose.
    url = f"/api/v1/org/months/{december}/seat-keeps/{member}"
    assert error_code(await client.delete(url, headers=teacher)) == "CLASS_FULL"
    assert error_code(await decide(client, teacher, december, member, "keep", hours=24)) == "CLASS_FULL"
    s = (await decide(client, teacher, december, member, "keep", hours=24, allow_over_limit=True)).json()
    assert s["over_by"] == 1 and kinds(s) == ["paying", "kept"]
    s = (await client.delete(url, headers=teacher)).json()                       # the ordinary rule: kept too
    assert kinds(s) == ["paying", "kept"]
    await decide(client, teacher, december, member, "release")
    s = (await client.delete(url, headers=teacher, params={"allow_over_limit": True})).json()
    assert s["over_by"] == 1
    assert (await client.delete(url, headers=teacher)).status_code == 200        # nothing to undo is fine


async def test_keep_longer(client: AsyncClient, teacher: Headers, new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=1, registration="closed")
    cid, slug = k["class"]["id"], k["class"]["slug"]
    await settings(client, teacher, cid, registration="open")
    old, fresh = await new_student(), await new_student()
    member = await member_id(client, old)
    await buy(client, old, cid, k["months"]["open"]["id"])
    december = await open_december(client, teacher, k)
    kept = (await decide(client, teacher, december, member, "keep", hours=240)).json()["seats"][0]["held_until"]
    await renewal_passed(december)
    s = await seats(client, teacher, cid, december)
    assert kinds(s) == ["kept"] and s["seats"][0]["held_until"] == kept
    view = (await client.get(f"/api/v1/student/classes/{slug}", headers=old)).json()
    assert {(m["seat"] or {}).get("kept_until") for m in view["months"]} == {kept, None}
    assert error_code(await checkout(client, fresh, cid, december)) == "CLASS_FULL"
    # It ends too.
    async with AdminSession() as a, a.begin():
        await a.execute(text("UPDATE seat_keeps SET keep_until = now() - interval '1 second' WHERE class_id = :c"),
                        {"c": cid})
    assert (await seats(client, teacher, cid, december))["taken"] == 0
    # And brings back someone who came too late, left and rejoined.
    await client.delete(f"/api/v1/student/classes/{slug}/enroll", headers=old)
    assert error_code(await decide(client, teacher, december, member, "keep", hours=24)) == "NOT_RETURNING"
    await client.post(f"/api/v1/student/classes/{slug}/enroll", headers=old)
    assert kinds((await decide(client, teacher, december, member, "keep", hours=24)).json()) == ["kept"]
    await settings(client, teacher, cid, registration="closed")
    await buy(client, old, cid, december)


async def test_keep_validation_and_permission(client: AsyncClient, sms: FakeSms, seed: Seed, teacher: Headers,  # noqa: F811
                                              members: AddMember, new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=3)
    cid, november = k["class"]["id"], k["months"]["open"]["id"]
    old, fresh = await new_student(), await new_student()
    member, stranger = await member_id(client, old), await member_id(client, fresh)
    await buy(client, old, cid, november)
    december = k["months"]["upcoming"]["id"]
    assert error_code(await decide(client, teacher, december, member, "release")) == "MONTH_NOT_OPEN"
    await open_december(client, teacher, k)
    assert error_code(await decide(client, teacher, december, stranger, "release")) == "NOT_RETURNING"
    assert error_code(await decide(client, teacher, december, str(uuid4()), "release")) == "NOT_RETURNING"
    for bad in ({"action": "keep"}, {"action": "release", "keep_until": "2027-01-01T00:00:00Z"}, {"action": "hold"},
                {"action": "keep", "keep_until": "2027-01-01T00:00:00"}):
        r = await client.put(f"/api/v1/org/months/{december}/seat-keeps/{member}", headers=teacher, json=bad)
        assert r.status_code == 422
    for hours in (-1, 24 * 61):
        assert error_code(await decide(client, teacher, december, member, "keep", hours=hours)) == "KEEP_UNTIL_INVALID"

    other_teacher = await auth_headers(client, sms, seed.a, await members(seed.a, "teacher"))
    other_org = await auth_headers(client, sms, seed.b, seed.b.teacher_phone)
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    for who, status in ((other_teacher, 404), (other_org, 404), (old, 403), (owner, 200)):
        assert (await decide(client, who, december, member, "release")).status_code == status
        if status != 200:
            assert (await client.delete(f"/api/v1/org/months/{december}/seat-keeps/{member}",
                                        headers=who)).status_code == status
    async with AdminSession() as s:
        log = (await s.execute(text("SELECT action, details->>'student_member_id' AS who FROM audit_logs "
                                    "WHERE entity_id = :m AND action LIKE 'seat.%'"), {"m": december})).all()
    assert [(r.action, r.who) for r in log] == [("seat.release", member)]
    await client.delete(f"/api/v1/org/months/{december}/seat-keeps/{member}", headers=owner)
    await buy(client, old, cid, december)
    assert error_code(await decide(client, teacher, december, member, "release")) == "ALREADY_HAS_ACCESS"


async def test_seat_keeps_are_isolated(client: AsyncClient, seed: Seed, teacher: Headers,  # noqa: F811
                                       new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher, seat_limit=3)
    old = await new_student()
    member = await member_id(client, old)
    await buy(client, old, k["class"]["id"], k["months"]["open"]["id"])
    december = await open_december(client, teacher, k)
    assert (await decide(client, teacher, december, member, "release")).status_code == 200
    async with tenant_transaction(seed.b.id) as s:
        assert (await s.execute(text("SELECT count(*) FROM seat_keeps"))).scalar_one() == 0
        assert (await s.execute(text("UPDATE seat_keeps SET decided_at = now()"))).rowcount == 0  # type: ignore[attr-defined]
        assert (await s.execute(text("DELETE FROM seat_keeps"))).rowcount == 0  # type: ignore[attr-defined]
    async with tenant_transaction(seed.a.id) as s:
        assert (await s.execute(text("SELECT count(*) FROM seat_keeps"))).scalar_one() == 1
    with pytest.raises(DBAPIError):                              # another tenant's class, even with its own tenant id
        async with tenant_transaction(seed.b.id) as s:
            await s.execute(text("""
                INSERT INTO seat_keeps (tenant_id, class_id, class_month_id, student_member_id, action, decided_by)
                VALUES (current_tenant_id(), :c, :mo, :m, 'release', :by)
            """), {"c": UUID(k["class"]["id"]), "mo": UUID(december), "m": UUID(member), "by": seed.b.member_id})


async def test_without_a_limit_nothing_is_promised(client: AsyncClient, teacher: Headers,  # noqa: F811
                                                   new_student: NewStudent) -> None:  # noqa: F811
    k = await monthly_class(client, teacher)
    cid, slug = k["class"]["id"], k["class"]["slug"]
    h = await new_student()
    await buy(client, h, cid, k["months"]["open"]["id"])
    december = await open_december(client, teacher, k)
    view = (await client.get(f"/api/v1/student/classes/{slug}", headers=h)).json()
    assert all((m["seat"] or {}).get("kept_until") is None for m in view["months"])
    assert (await checkout(client, await new_student(), cid, december)).status_code == 201
