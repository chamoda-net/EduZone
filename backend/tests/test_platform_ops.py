"""Phase 8: the platform admin's new screens. Subjects, listing an organization on the marketplace, users and
their devices, checkouts with a retry for a half-fulfilled one, and the audit log."""

from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AdminSession, AppSession
from app.modules.checkout import service as checkout_service
from tests.conftest import FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_cart import fill, pay, shop  # noqa: F401  (fixture)
from tests.test_checkout import ledger
from tests.test_learn import main_login, user_id_of
from tests.test_market import published
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
P = "/api/v1/platform"


@pytest.fixture
async def new_subjects() -> AsyncIterator[list[str]]:
    slugs: list[str] = []
    yield slugs
    if slugs:
        async with AdminSession() as s, s.begin():
            await s.execute(text("DELETE FROM subjects WHERE slug = ANY(:s)"), {"s": slugs})


# --- subjects -------------------------------------------------------------------------------------

async def test_subjects(client: AsyncClient, ph: Headers, new_subjects: list[str]) -> None:
    slug = f"t-{uuid4().hex[:8]}"
    new_subjects.append(slug)
    created = await client.post(f"{P}/subjects", headers=ph, json={"name": "Agriculture", "slug": slug,
                                                                   "sort_order": 90})
    assert created.status_code == 201, created.text
    sub = created.json()
    assert sub["is_active"] and sub["classes"] == 0
    assert any(s["slug"] == slug for s in (await client.get("/api/v1/market/subjects")).json())

    # A slug is unique, never a site route, and fixed once created.
    again = await client.post(f"{P}/subjects", headers=ph, json={"name": "Agri 2", "slug": slug})
    assert again.status_code == 409 and error_code(again) == "SLUG_TAKEN"
    reserved = await client.post(f"{P}/subjects", headers=ph, json={"name": "Learn", "slug": "learn"})
    assert reserved.status_code == 422 and error_code(reserved) == "SLUG_RESERVED"
    assert (await client.patch(f"{P}/subjects/{sub['id']}", headers=ph, json={"slug": "x"})).status_code == 422

    # Hiding takes it off the marketplace; renaming and ordering are kept.
    hidden = await client.patch(f"{P}/subjects/{sub['id']}", headers=ph,
                                json={"is_active": False, "name": "Agricultural Science"})
    assert hidden.status_code == 200 and hidden.json()["name"] == "Agricultural Science"
    assert not any(s["slug"] == slug for s in (await client.get("/api/v1/market/subjects")).json())
    listed = (await client.get(f"{P}/subjects", headers=ph)).json()
    assert any(s["slug"] == slug and not s["is_active"] for s in listed)
    assert any(s["slug"] == "physics" for s in listed)

    audit = (await client.get(f"{P}/audit", headers=ph, params={"entity_id": sub["id"]})).json()["items"]
    assert [a["action"] for a in audit] == ["platform.subject.update", "platform.subject.create"]
    assert audit[0]["tenant_id"] is None and audit[0]["actor_name"] == "EduZone Staff"


async def test_subjects_need_an_admin(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    owner = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    assert (await client.get(f"{P}/subjects", headers=owner)).status_code == 401
    assert (await client.get(f"{P}/subjects")).status_code == 401


# --- listing on the marketplace ------------------------------------------------------------------

async def test_unlisting_hides_an_organization(client: AsyncClient, ph: Headers, seed: Seed, sms: FakeSms) -> None:
    teacher = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    await published(client, teacher)

    async def on_market() -> int:
        async with AppSession() as s:   # the marketplace's read path
            return int((await s.execute(text("SELECT count(*) FROM public_classes WHERE tenant_id = :t"),
                                        {"t": seed.a.id})).scalar_one())

    assert await on_market() >= 1
    try:
        r = await client.patch(f"{P}/tenants/{seed.a.id}", headers=ph, json={"is_listed": False})
        assert r.status_code == 200 and r.json()["is_listed"] is False
        assert await on_market() == 0
        # Still active: its console and its students keep working.
        assert (await client.get(f"/api/v1/teach/{seed.a.slug}/classes", headers=teacher)).status_code == 200
        audit = (await client.get(f"{P}/audit", headers=ph, params={"tenant_id": str(seed.a.id)})).json()["items"]
        assert audit[0]["action"] == "platform.tenant.unlist" and audit[0]["tenant_name"] == seed.a.name
        assert (await client.patch(f"{P}/tenants/{seed.a.id}", headers=ph,
                                   json={"is_listed": None})).status_code == 422
    finally:
        await client.patch(f"{P}/tenants/{seed.a.id}", headers=ph, json={"is_listed": True})
    assert await on_market() >= 1


# --- users and devices ----------------------------------------------------------------------------

async def test_users_and_devices(client: AsyncClient, ph: Headers, sms: FakeSms,
                                 phones: Callable[[], str]) -> None:
    phone = phones()
    student = await main_login(client, sms, phone)
    user_id = await user_id_of(phone)

    for q in (phone, "0" + phone[3:], phone[-6:]):
        found = (await client.get(f"{P}/users", headers=ph, params={"q": q})).json()
        assert [u["id"] for u in found][:1] == [str(user_id)], q
    assert (await client.get(f"{P}/users", headers=ph, params={"q": "x"})).status_code == 422

    detail = (await client.get(f"{P}/users/{user_id}", headers=ph)).json()
    assert detail["phone"] == phone and detail["active_sessions"] == 1 and detail["phone_verified"]
    assert detail["sessions"][0]["active"] and len(detail["devices"]) == 1
    assert (await client.get("/api/v1/auth/me", headers=student)).status_code == 200

    # Forgetting the device ends its session; the student's token stops working.
    device = detail["devices"][0]["id"]
    r = await client.delete(f"{P}/users/{user_id}/devices/{device}", headers=ph)
    assert r.status_code == 200 and r.json() == {"sessions_ended": 1}
    assert (await client.get("/api/v1/auth/me", headers=student)).status_code == 401
    detail = (await client.get(f"{P}/users/{user_id}", headers=ph)).json()
    assert detail["devices"] == [] and detail["active_sessions"] == 0
    assert detail["sessions"][0]["revoke_reason"] == "platform_admin"
    assert (await client.delete(f"{P}/users/{user_id}/devices/{device}", headers=ph)).status_code == 404

    # Sign out everywhere.
    student = await main_login(client, sms, phone)
    assert (await client.post(f"{P}/users/{user_id}/sign-out", headers=ph)).json() == {"sessions_ended": 1}
    assert (await client.get("/api/v1/auth/me", headers=student)).status_code == 401
    assert (await client.post(f"{P}/users/{uuid4()}/sign-out", headers=ph)).status_code == 404

    audit = (await client.get(f"{P}/audit", headers=ph, params={"entity_id": str(user_id)})).json()["items"]
    assert [a["action"] for a in audit] == ["platform.user.sign_out", "platform.user.forget_device"]


# --- checkouts ---------------------------------------------------------------------------------------

async def test_stuck_checkout_is_retried(client: AsyncClient, ph: Headers, seed: Seed, shop: dict[str, Any],  # noqa: F811
                                         monkeypatch: pytest.MonkeyPatch) -> None:
    h = shop["student"]
    await fill(client, shop)
    out, form = await pay(client, h)
    checkout_id = out["checkout"]["id"]

    real = checkout_service.fulfil_order

    async def broken_in_b(session: Any, p: Any, event: Any, **kw: Any) -> None:
        if (await session.execute(text("SELECT current_tenant_id()"))).scalar_one() == seed.b.id:
            raise RuntimeError("database hiccup")
        await real(session, p, event, **kw)

    monkeypatch.setattr(checkout_service, "fulfil_order", broken_in_b)
    with pytest.raises(RuntimeError):
        await checkout_service.process_notification("fake", form)

    stuck = (await client.get(f"{P}/checkouts", headers=ph, params={"stuck": "true"})).json()["items"]
    row = next(c for c in stuck if c["id"] == checkout_id)
    assert row["status"] == "pending" and row["payment_status"] == "succeeded"
    assert (row["orders"], row["orders_paid"]) == (2, 1)
    detail = (await client.get(f"{P}/checkouts/{checkout_id}", headers=ph)).json()
    assert sorted(o["status"] for o in detail["order_list"]) == ["paid", "pending"]
    assert detail["attempts"][0]["card_last4"] == "4242"

    # Still broken: the retry reports the error and changes nothing.
    failed = (await client.post(f"{P}/checkouts/{checkout_id}/retry", headers=ph)).json()
    assert failed["outcome"].startswith("error") and failed["checkout"]["stuck"]

    monkeypatch.setattr(checkout_service, "fulfil_order", real)
    done = await client.post(f"{P}/checkouts/{checkout_id}/retry", headers=ph)
    assert done.status_code == 200 and done.json()["outcome"] == "paid"
    assert done.json()["checkout"]["status"] == "paid" and not done.json()["checkout"]["stuck"]
    for tenant in (seed.a.id, seed.b.id):
        assert (await ledger(tenant))["sales"] == 1      # A not booked twice
    assert (await client.get(f"/api/v1/me/checkouts/{checkout_id}", headers=h)).json()["status"] == "paid"

    # Nothing left to retry; the gateway's own redelivery is now harmless too.
    again = await client.post(f"{P}/checkouts/{checkout_id}/retry", headers=ph)
    assert again.status_code == 409 and error_code(again) == "CHECKOUT_NOT_STUCK"
    assert await checkout_service.process_notification("fake", form) == "paid"
    for tenant in (seed.a.id, seed.b.id):
        assert (await ledger(tenant))["sales"] == 1
    audit = (await client.get(f"{P}/audit", headers=ph, params={"entity_id": checkout_id})).json()["items"]
    assert [a["details"]["outcome"][:5] for a in audit] == ["paid", "error"]


async def test_checkout_list_filters_and_pages(client: AsyncClient, ph: Headers, shop: dict[str, Any]) -> None:  # noqa: F811
    await fill(client, shop)
    out, _ = await pay(client, shop["student"])
    pending = (await client.get(f"{P}/checkouts", headers=ph, params={"status": "pending"})).json()["items"]
    assert any(c["id"] == out["checkout"]["id"] and not c["stuck"] for c in pending)
    assert all(c["status"] == "pending" for c in pending)
    first = (await client.get(f"{P}/checkouts", headers=ph, params={"limit": 1})).json()
    assert len(first["items"]) == 1 and first["next_cursor"]
    nxt = (await client.get(f"{P}/checkouts", headers=ph, params={"limit": 1, "cursor": first["next_cursor"]})).json()
    assert nxt["items"][0]["id"] != first["items"][0]["id"]
    assert (await client.get(f"{P}/checkouts/{uuid4()}", headers=ph)).status_code == 404


# --- audit log ---------------------------------------------------------------------------------------

async def test_audit_log_pages_and_filters(client: AsyncClient, ph: Headers, padmin: Any,  # noqa: F811
                                           new_subjects: list[str]) -> None:
    for _ in range(3):
        slug = f"t-{uuid4().hex[:8]}"
        new_subjects.append(slug)
        await client.post(f"{P}/subjects", headers=ph, json={"name": "Temp subject", "slug": slug})
    params: dict[str, Any] = {"actor_id": str(padmin.user_id), "action": "platform.subject.", "limit": 2}
    first = (await client.get(f"{P}/audit", headers=ph, params=params)).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = (await client.get(f"{P}/audit", headers=ph, params={**params, "cursor": first["next_cursor"]})).json()
    ids = [a["id"] for a in first["items"] + rest["items"]]
    assert len(ids) == 3 and ids == sorted(ids, reverse=True)
    # A prefix is literal: "_" doesn't match any character.
    assert (await client.get(f"{P}/audit", headers=ph, params={"action": "platform_"})).json()["items"] == []
    assert (await client.get(f"{P}/audit", headers=ph, params={"cursor": "abc"})).status_code == 400
