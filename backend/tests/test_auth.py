"""Phone OTP login, sessions, JWT and the one-device rule (CLAUDE.md sections 10-11)."""

from collections.abc import Callable

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from app.modules.auth.phone import normalize_phone
from tests.conftest import FakeSms, Seed, SeededTenant

Phones = Callable[[], str]


# --- helpers ----------------------------------------------------------------------

async def request_code(client: AsyncClient, tenant: SeededTenant, phone: str) -> Response:
    return await client.post("/api/v1/auth/otp/request", json={"phone": phone}, headers={"host": tenant.host})


async def verify(client: AsyncClient, tenant: SeededTenant, phone: str, code: str,
                 device: str = "device-0001", name: str | None = "Test Student") -> Response:
    body = {"phone": phone, "code": code, "device_id": device}
    if name is not None:
        body["full_name"] = name
    return await client.post("/api/v1/auth/otp/verify", json=body, headers={"host": tenant.host})


async def skip_cooldown(phone: str) -> None:
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE otp_codes SET created_at = created_at - interval '2 minutes' "
                             "WHERE destination = :p"), {"p": phone})


async def login(client: AsyncClient, sms: FakeSms, tenant: SeededTenant, phone: str,
                device: str = "device-0001") -> dict[str, str]:
    await skip_cooldown(phone)
    assert (await request_code(client, tenant, phone)).status_code == 202
    resp = await verify(client, tenant, phone, sms.last_code(phone), device=device)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def me(client: AsyncClient, tenant: SeededTenant, access: str) -> Response:
    return await client.get("/api/v1/auth/me",
                            headers={"host": tenant.host, "authorization": f"Bearer {access}"})


async def refresh(client: AsyncClient, tenant: SeededTenant, token: str) -> Response:
    return await client.post("/api/v1/auth/refresh", json={"refresh_token": token},
                             headers={"host": tenant.host})


def error_code(resp: Response) -> str:
    return resp.json()["error"]["code"]


# --- phone numbers ------------------------------------------------------------------

@pytest.mark.parametrize(("raw", "expected"), [
    ("0771234567", "+94771234567"),
    ("077 123 4567", "+94771234567"),
    ("94771234567", "+94771234567"),
    ("+94771234567", "+94771234567"),
    ("+447911123456", "+447911123456"),
])
def test_normalize_phone(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "12345", "077123456", "+0771234567", "phone"])
def test_normalize_phone_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_phone(raw)


async def test_invalid_phone_is_422(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    resp = await request_code(client, seed.a, "12345")
    assert resp.status_code == 422
    assert error_code(resp) == "VALIDATION_ERROR"
    assert sms.sent == []


# --- requesting a code ----------------------------------------------------------------

async def test_request_sends_branded_six_digit_code(client: AsyncClient, seed: Seed, sms: FakeSms,
                                                    phones: Phones) -> None:
    phone = phones()
    resp = await request_code(client, seed.a, phone)
    assert resp.status_code == 202
    assert resp.json() == {"expires_in": 300, "resend_after": 60}
    [(to, message)] = sms.sent
    assert to == phone
    assert message.split()[0].isdigit() and len(message.split()[0]) == 6
    assert seed.a.name in message


async def test_stored_code_is_hashed(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    await request_code(client, seed.a, phone)
    async with AdminSession() as s:
        stored = (await s.execute(text("SELECT code_hash FROM otp_codes WHERE destination = :p"),
                                  {"p": phone})).scalar_one()
    assert sms.last_code(phone) not in stored
    assert len(stored) == 64


async def test_resend_cooldown(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    assert (await request_code(client, seed.a, phone)).status_code == 202
    resp = await request_code(client, seed.a, phone)
    assert resp.status_code == 429
    assert error_code(resp) == "OTP_RATE_LIMITED"
    assert len(sms.sent) == 1


async def test_hourly_limit_per_phone(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    async with AdminSession() as s, s.begin():
        for _ in range(5):
            await s.execute(text("INSERT INTO otp_codes (destination, purpose, code_hash, expires_at, created_at) "
                                 "VALUES (:p, 'login', 'x', now(), now() - interval '10 minutes')"), {"p": phone})
    resp = await request_code(client, seed.a, phone)
    assert resp.status_code == 429
    assert sms.sent == []


async def test_hourly_limit_per_ip(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    first = phones()
    assert (await request_code(client, seed.a, first)).status_code == 202
    async with AdminSession() as s, s.begin():
        ip = (await s.execute(text("SELECT host(request_ip) FROM otp_codes WHERE destination = :p"),
                              {"p": first})).scalar_one()
        for _ in range(19):
            await s.execute(text("INSERT INTO otp_codes (destination, purpose, code_hash, expires_at, request_ip) "
                                 "VALUES (:p, 'login', 'x', now(), CAST(:ip AS inet))"), {"p": first, "ip": ip})
    resp = await request_code(client, seed.a, phones())
    assert resp.status_code == 429


async def test_unknown_tenant_cannot_request(client: AsyncClient, sms: FakeSms, phones: Phones) -> None:
    resp = await client.post("/api/v1/auth/otp/request", json={"phone": phones()},
                             headers={"host": "nobody-here.eduzone.lk"})
    assert resp.status_code == 404
    assert sms.sent == []


# --- verifying a code -------------------------------------------------------------------

async def test_signup_needs_name_without_spending_the_code(client: AsyncClient, seed: Seed, sms: FakeSms,
                                                           phones: Phones) -> None:
    phone = phones()
    await request_code(client, seed.a, phone)
    code = sms.last_code(phone)

    resp = await verify(client, seed.a, phone, code, name=None)
    assert resp.status_code == 400
    assert error_code(resp) == "NAME_REQUIRED"

    resp = await verify(client, seed.a, phone, code, name="Nimal Perera")
    assert resp.status_code == 200
    tokens = resp.json()
    assert tokens["token_type"] == "bearer" and tokens["expires_in"] == 900

    profile = (await me(client, seed.a, tokens["access_token"])).json()
    assert profile["full_name"] == "Nimal Perera"
    assert profile["phone"] == phone
    assert profile["role"] == "student"


async def test_existing_user_keeps_name(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    await request_code(client, seed.a, seed.a.teacher_phone)
    resp = await verify(client, seed.a, seed.a.teacher_phone, sms.last_code(seed.a.teacher_phone),
                        name="Someone Else")
    profile = (await me(client, seed.a, resp.json()["access_token"])).json()
    assert profile["full_name"] == "Teacher a"
    assert profile["role"] == "teacher"


async def test_wrong_code_counts_and_locks(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    await request_code(client, seed.a, phone)
    good = sms.last_code(phone)
    bad = f"{(int(good) + 1) % 10**6:06d}"
    for _ in range(5):
        resp = await verify(client, seed.a, phone, bad)
        assert error_code(resp) == "OTP_INVALID"
    resp = await verify(client, seed.a, phone, good)
    assert resp.status_code == 429
    assert error_code(resp) == "OTP_TOO_MANY_ATTEMPTS"


async def test_expired_code_rejected(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    await request_code(client, seed.a, phone)
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE otp_codes SET expires_at = now() - interval '1 second' "
                             "WHERE destination = :p"), {"p": phone})
    resp = await verify(client, seed.a, phone, sms.last_code(phone))
    assert error_code(resp) == "OTP_INVALID"


async def test_code_works_once(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    await request_code(client, seed.a, phone)
    code = sms.last_code(phone)
    assert (await verify(client, seed.a, phone, code)).status_code == 200
    assert error_code(await verify(client, seed.a, phone, code)) == "OTP_INVALID"


async def test_suspended_member_cannot_sign_in(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE tenant_members SET status = 'suspended' WHERE id = :id"),
                        {"id": seed.a.member_id})
    await request_code(client, seed.a, seed.a.teacher_phone)
    resp = await verify(client, seed.a, seed.a.teacher_phone, sms.last_code(seed.a.teacher_phone))
    assert resp.status_code == 403
    assert error_code(resp) == "ACCOUNT_SUSPENDED"


# --- access tokens and sessions --------------------------------------------------------

@pytest.mark.parametrize("header", ["", "Bearer", "Bearer not-a-jwt", "Basic abc"])
async def test_bad_authorization_is_401(client: AsyncClient, seed: Seed, header: str) -> None:
    resp = await client.get("/api/v1/auth/me", headers={"host": seed.a.host, "authorization": header})
    assert resp.status_code == 401
    assert error_code(resp) == "UNAUTHORIZED"


async def test_token_from_tenant_a_rejected_on_tenant_b(client: AsyncClient, seed: Seed, sms: FakeSms,
                                                        phones: Phones) -> None:
    tokens = await login(client, sms, seed.a, phones())
    assert (await me(client, seed.a, tokens["access_token"])).status_code == 200
    resp = await me(client, seed.b, tokens["access_token"])
    assert resp.status_code == 401
    assert error_code(resp) == "UNAUTHORIZED"
    assert (await refresh(client, seed.b, tokens["refresh_token"])).status_code == 401


async def test_one_device_per_student(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    first = await login(client, sms, seed.a, phone, device="phone-0001")
    second = await login(client, sms, seed.a, phone, device="laptop-0001")

    resp = await me(client, seed.a, first["access_token"])
    assert resp.status_code == 401
    assert error_code(resp) == "SESSION_REVOKED"
    assert error_code(await refresh(client, seed.a, first["refresh_token"])) == "SESSION_INVALID"
    assert (await me(client, seed.a, second["access_token"])).status_code == 200


async def test_staff_may_use_several_devices(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    first = await login(client, sms, seed.a, seed.a.teacher_phone, device="phone-0001")
    second = await login(client, sms, seed.a, seed.a.teacher_phone, device="laptop-0001")
    assert (await me(client, seed.a, first["access_token"])).status_code == 200
    assert (await me(client, seed.a, second["access_token"])).status_code == 200


async def test_one_device_rule_is_per_tenant(client: AsyncClient, seed: Seed, sms: FakeSms,
                                             phones: Phones) -> None:
    phone = phones()
    in_a = await login(client, sms, seed.a, phone)
    in_b = await login(client, sms, seed.b, phone)
    assert (await me(client, seed.a, in_a["access_token"])).status_code == 200
    assert (await me(client, seed.b, in_b["access_token"])).status_code == 200


async def test_refresh_rotates_token(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    tokens = await login(client, sms, seed.a, phones())
    resp = await refresh(client, seed.a, tokens["refresh_token"])
    assert resp.status_code == 200
    rotated = resp.json()
    assert rotated["refresh_token"] != tokens["refresh_token"]
    assert (await me(client, seed.a, rotated["access_token"])).status_code == 200
    assert error_code(await refresh(client, seed.a, tokens["refresh_token"])) == "SESSION_INVALID"
    assert (await refresh(client, seed.a, rotated["refresh_token"])).status_code == 200


async def test_logout_ends_session(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    tokens = await login(client, sms, seed.a, phones())
    headers = {"host": seed.a.host, "authorization": f"Bearer {tokens['access_token']}"}
    assert (await client.post("/api/v1/auth/logout", headers=headers)).status_code == 204
    assert error_code(await me(client, seed.a, tokens["access_token"])) == "SESSION_REVOKED"
    assert (await refresh(client, seed.a, tokens["refresh_token"])).status_code == 401


async def test_suspension_ends_existing_sessions(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    tokens = await login(client, sms, seed.a, seed.a.teacher_phone)
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE tenant_members SET status = 'suspended' WHERE id = :id"),
                        {"id": seed.a.member_id})
    assert error_code(await me(client, seed.a, tokens["access_token"])) == "SESSION_REVOKED"
    assert (await refresh(client, seed.a, tokens["refresh_token"])).status_code == 401


async def test_refresh_token_is_stored_hashed(client: AsyncClient, seed: Seed, sms: FakeSms,
                                              phones: Phones) -> None:
    tokens = await login(client, sms, seed.a, phones())
    async with AdminSession() as s:
        stored = (await s.execute(text("SELECT refresh_token_hash FROM user_sessions "
                                       "WHERE tenant_id = :t"), {"t": seed.a.id})).scalars().all()
    assert tokens["refresh_token"] not in stored


# --- isolation: user_sessions (CLAUDE.md section 5, rule 8) ------------------------------

async def test_user_sessions_isolated(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    await login(client, sms, seed.a, phone)
    await login(client, sms, seed.b, phone)
    async with tenant_transaction(seed.a.id) as session:
        tenants = (await session.execute(text(
            "SELECT s.tenant_id FROM user_sessions s JOIN users u ON u.id = s.user_id WHERE u.phone = :p"
        ), {"p": phone})).scalars().all()
        revoked_elsewhere = await session.execute(text(
            "UPDATE user_sessions SET revoked_at = now() WHERE tenant_id = :b"), {"b": seed.b.id})
    assert tenants == [seed.a.id]
    assert revoked_elsewhere.rowcount == 0  # type: ignore[attr-defined]
