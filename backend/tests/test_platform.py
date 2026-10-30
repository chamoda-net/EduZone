"""Step 9: platform admin. Sign-in with SMS + authenticator, network allowlist, organizations,
payments, payouts posted to the ledger."""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import AdminSession
from app.modules.platform import totp
from tests.conftest import AddMember, FakeSms, Seed, SeededTenant, purge_tenants
from tests.helpers import auth_headers, email_for, error_code, skip_cooldown
from tests.test_money import sell

Headers = dict[str, str]


@dataclass
class PlatformAdminUser:
    user_id: UUID
    phone: str
    secret: str


@pytest.fixture
async def padmin(phones: Callable[[], str]) -> AsyncIterator[PlatformAdminUser]:
    phone, secret = phones(), totp.new_secret()
    async with AdminSession() as s, s.begin():
        user_id = (await s.execute(text(
            "INSERT INTO users (phone, full_name, is_platform_admin) VALUES (:p, 'EduZone Staff', true) RETURNING id"
        ), {"p": phone})).scalar_one()
        await s.execute(text("INSERT INTO platform_admins (user_id, totp_secret) VALUES (:u, :s)"),
                        {"u": user_id, "s": secret})
    yield PlatformAdminUser(user_id, phone, secret)
    async with AdminSession() as s, s.begin():   # platform-level audit rows have no tenant
        await s.execute(text("DELETE FROM audit_logs WHERE actor_user_id = :u AND tenant_id IS NULL"), {"u": user_id})


@pytest.fixture
async def created_tenants() -> AsyncIterator[list[UUID]]:
    ids: list[UUID] = []
    yield ids
    if ids:
        purge_tenants(ids)


async def platform_login(client: AsyncClient, sms: FakeSms, a: PlatformAdminUser, *, totp_code: str | None = None,
                         step_offset: int = 0) -> Any:
    await skip_cooldown(a.phone)
    assert (await client.post("/api/v1/platform/auth/otp/request", json={"phone": a.phone})).status_code == 202
    code = totp_code or totp.code_at(a.secret, totp.current_step() + step_offset)
    return await client.post("/api/v1/platform/auth/login",
                             json={"phone": a.phone, "code": sms.last_code(a.phone), "totp": code})


@pytest.fixture
async def ph(client: AsyncClient, sms: FakeSms, padmin: PlatformAdminUser) -> Headers:
    resp = await platform_login(client, sms, padmin)
    assert resp.status_code == 200, resp.text
    return {"authorization": f"Bearer {resp.json()['access_token']}"}


# --- authenticator codes -----------------------------------------------------------------

def test_totp_rfc6238_vector() -> None:
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"         # ASCII "12345678901234567890"
    assert totp.code_at(secret, 59 // 30) == "287082"
    assert totp.verify(secret, "287082", last_used_step=0, now=59) == 1
    assert totp.verify(secret, "287082", last_used_step=1, now=59) is None     # replay refused
    assert totp.verify(secret, "000000", last_used_step=0, now=59) is None
    assert totp.provisioning_uri(secret, "+94771234567").startswith("otpauth://totp/EduZone%20Admin:")


# --- sign-in --------------------------------------------------------------------------------

async def test_admin_signs_in_with_both_factors(client: AsyncClient, sms: FakeSms, padmin: PlatformAdminUser) -> None:
    resp = await platform_login(client, sms, padmin)
    assert resp.status_code == 200
    h = {"authorization": f"Bearer {resp.json()['access_token']}"}
    assert (await client.get("/api/v1/platform/auth/me", headers=h)).json()["full_name"] == "EduZone Staff"
    assert "admin sign-in code" in sms.sent[-1][1]
    # Refresh rotates; logout ends the session.
    rotated = await client.post("/api/v1/platform/auth/refresh", json={"refresh_token": resp.json()["refresh_token"]})
    assert rotated.status_code == 200
    assert (await client.post("/api/v1/platform/auth/logout", headers=h)).status_code == 204
    assert error_code(await client.get("/api/v1/platform/auth/me", headers=h)) == "SESSION_REVOKED"


async def test_wrong_authenticator_code(client: AsyncClient, sms: FakeSms, padmin: PlatformAdminUser) -> None:
    resp = await platform_login(client, sms, padmin, totp_code="000000")
    assert resp.status_code == 401 and error_code(resp) == "INVALID_LOGIN"


async def test_authenticator_code_works_once(client: AsyncClient, sms: FakeSms, padmin: PlatformAdminUser) -> None:
    code = totp.code_at(padmin.secret, totp.current_step())
    assert (await platform_login(client, sms, padmin, totp_code=code)).status_code == 200
    assert error_code(await platform_login(client, sms, padmin, totp_code=code)) == "INVALID_LOGIN"


async def test_non_admins_get_no_code(client: AsyncClient, sms: FakeSms, seed: Seed) -> None:
    resp = await client.post("/api/v1/platform/auth/otp/request", json={"phone": seed.a.teacher_phone})
    assert resp.status_code == 202                      # same answer as for an admin...
    assert sms.sent == []                               # ...but nothing is sent


async def test_tokens_dont_cross(client: AsyncClient, sms: FakeSms, seed: Seed, ph: Headers) -> None:
    tenant_h = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    resp = await client.get("/api/v1/platform/tenants", headers={"authorization": tenant_h["authorization"]})
    assert resp.status_code == 401
    resp = await client.get("/api/v1/auth/me", headers={**ph, "host": seed.a.host})
    assert resp.status_code == 401


async def test_network_allowlist(client: AsyncClient, ph: Headers) -> None:
    settings = get_settings()
    try:
        settings.platform_allowed_cidrs = ["192.0.2.0/24"]
        assert (await client.get("/api/v1/platform/tenants", headers=ph)).status_code == 404
        settings.platform_allowed_cidrs = ["10.0.0.0/8"]          # test clients use 10.x addresses
        assert (await client.get("/api/v1/platform/tenants", headers=ph)).status_code == 200
        settings.platform_allowed_cidrs, settings.environment = [], "production"
        assert (await client.get("/api/v1/platform/tenants", headers=ph)).status_code == 404  # must be configured
    finally:
        settings.platform_allowed_cidrs, settings.environment = [], "local"


# --- organizations --------------------------------------------------------------------------

async def test_create_organization_and_owner(client: AsyncClient, sms: FakeSms, phones: Callable[[], str],
                                             ph: Headers, created_tenants: list[UUID]) -> None:
    slug, owner_phone = f"new-{uuid4().hex[:8]}", phones()
    owner_email = email_for(owner_phone)
    resp = await client.post("/api/v1/platform/tenants", headers=ph, json={
        "name": "Sipsala Institute", "slug": slug, "org_type": "institute", "commission_bps": 1500,
        "owner_email": owner_email.upper(), "owner_name": "Mrs Perera", "primary_color": "#0F766E"})
    assert resp.status_code == 201, resp.text
    created = resp.json()
    created_tenants.append(UUID(created["tenant"]["id"]))
    assert created["tenant"]["status"] == "active" and created["tenant"]["commission_bps"] == 1500
    assert created["tenant"]["members"] == 1 and created["tenant"]["balance_due_cents"] == 0

    # A new owner has no password yet (they set one with "Forgot password") and no phone.
    async with AdminSession() as s, s.begin():
        owner = (await s.execute(text("SELECT email, password_hash, phone FROM users WHERE email = :e"),
                                 {"e": owner_email})).one()
        assert owner.password_hash is None and owner.phone is None
        # Simulate that: password set, phone verified (the helper below fills both in).
        await s.execute(text("UPDATE users SET phone = :p WHERE email = :e"), {"p": owner_phone, "e": owner_email})

    # Then the owner signs in on the new site.
    host = f"{slug}.{get_settings().base_domain}"
    assert (await client.get("/api/v1/public/tenant", headers={"host": host})).json()["name"] == "Sipsala Institute"
    site = SeededTenant(UUID(created["tenant"]["id"]), slug, "Sipsala Institute", host, uuid4(), owner_phone, uuid4())
    owner = await auth_headers(client, sms, site, owner_phone)
    assert (await client.get("/api/v1/auth/me", headers=owner)).json()["role"] == "owner"

    dup = await client.post("/api/v1/platform/tenants", headers=ph, json={
        "name": "Copy", "slug": slug, "owner_email": email_for(phones()), "owner_name": "X"})
    assert dup.status_code == 409 and error_code(dup) == "SLUG_TAKEN"
    reserved = await client.post("/api/v1/platform/tenants", headers=ph, json={
        "name": "Nope", "slug": "admin", "owner_email": email_for(phones()), "owner_name": "X"})
    assert reserved.status_code == 422

    async with AdminSession() as s:
        action = (await s.execute(text("SELECT action FROM audit_logs WHERE entity_id = :t"),
                                  {"t": created["tenant"]["id"]})).scalar_one()
    assert action == "platform.tenant.create"


async def test_suspend_takes_the_site_offline(client: AsyncClient, seed: Seed, ph: Headers) -> None:
    resp = await client.patch(f"/api/v1/platform/tenants/{seed.a.id}", headers=ph, json={"status": "suspended"})
    assert resp.status_code == 200 and resp.json()["status"] == "suspended"
    assert (await client.get("/api/v1/public/tenant", headers={"host": seed.a.host})).status_code == 404
    listed = (await client.get("/api/v1/platform/tenants?status=suspended", headers=ph)).json()
    assert str(seed.a.id) in {t["id"] for t in listed}
    bad = await client.patch(f"/api/v1/platform/tenants/{seed.a.id}", headers=ph, json={"commission_bps": None})
    assert bad.status_code == 422


# --- money: payments, balances, payouts -------------------------------------------------------

async def test_payments_and_payouts(client: AsyncClient, sms: FakeSms, seed: Seed, members: AddMember,
                                    ph: Headers) -> None:
    teacher = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    await sell(client, sms, seed, members, teacher)

    pays = (await client.get(f"/api/v1/platform/payments?tenant_id={seed.a.id}", headers=ph)).json()["items"]
    assert [(p["tenant_name"], p["status"], p["total_cents"], p["gateway"]) for p in pays] == [
        (seed.a.name, "paid", 200000, "fake")]
    row = (await client.get(f"/api/v1/platform/tenants/{seed.a.id}", headers=ph)).json()
    assert row["balance_due_cents"] == 154000 and row["sales_this_month_cents"] == 200000

    payout = {"amount_cents": 200000, "period_start": "2026-10-01", "period_end": "2026-10-31",
              "bank_reference": "BOC-TRX-0001"}
    too_much = await client.post(f"/api/v1/platform/tenants/{seed.a.id}/payouts", headers=ph, json=payout)
    assert too_much.status_code == 409 and error_code(too_much) == "PAYOUT_EXCEEDS_BALANCE"
    done = await client.post(f"/api/v1/platform/tenants/{seed.a.id}/payouts", headers=ph,
                             json={**payout, "amount_cents": 100000})
    assert done.status_code == 201 and done.json()["status"] == "sent"
    assert done.json()["created_by_name"] == "EduZone Staff"

    row = (await client.get(f"/api/v1/platform/tenants/{seed.a.id}", headers=ph)).json()
    assert row["balance_due_cents"] == 54000
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    cash = (await client.get("/api/v1/org/cashflow", headers=owner)).json()
    assert cash["balance_due_cents"] == 54000 and cash["totals"]["paid_out_cents"] == 100000
    history = (await client.get(f"/api/v1/platform/tenants/{seed.a.id}/payouts", headers=ph)).json()
    assert [p["bank_reference"] for p in history] == ["BOC-TRX-0001"]

    async with AdminSession() as s:
        unbalanced = (await s.execute(text("""
            SELECT count(*) FROM (SELECT ledger_tx_id FROM ledger_entries WHERE tenant_id = :t
                                  GROUP BY 1 HAVING sum(amount_cents) <> 0) x"""), {"t": seed.a.id})).scalar_one()
    assert unbalanced == 0

    bad_period = await client.post(f"/api/v1/platform/tenants/{seed.a.id}/payouts", headers=ph,
                                   json={**payout, "amount_cents": 1, "period_end": "2026-09-01"})
    assert bad_period.status_code == 422


async def test_tenant_staff_cannot_reach_platform(client: AsyncClient, sms: FakeSms, seed: Seed,
                                                  members: AddMember) -> None:
    owner = await auth_headers(client, sms, seed.a, await members(seed.a, "owner"))
    resp = await client.get("/api/v1/platform/payments", headers={"authorization": owner["authorization"]})
    assert resp.status_code == 401
