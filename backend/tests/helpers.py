"""Shared HTTP helpers for tests."""

from collections.abc import Callable

from httpx import AsyncClient, Response
from sqlalchemy import text

from app.core.db import AdminSession
from app.modules.auth.passwords import hash_password
from tests.conftest import FakeSms, SeededTenant

Phones = Callable[[], str]


PASSWORD = "Test-password-123"
_PASSWORD_HASH: list[str] = []


def _password_hash() -> str:
    if not _PASSWORD_HASH:
        _PASSWORD_HASH.append(hash_password(PASSWORD))
    return _PASSWORD_HASH[0]


def email_for(phone: str) -> str:
    return f"u{phone.lstrip('+')}@example.com"


async def ensure_account(phone: str, name: str = "Test Student") -> str:
    """A signed-up account for this phone (verified), with email_for(phone) and PASSWORD."""
    async with AdminSession() as s, s.begin():
        await s.execute(text("""
            INSERT INTO users (phone, email, full_name, password_hash, phone_verified_at, email_verified_at)
            VALUES (:p, :e, :n, :h, now(), now())
            ON CONFLICT (phone) DO UPDATE
                SET email = COALESCE(users.email, EXCLUDED.email), password_hash = EXCLUDED.password_hash,
                    phone_verified_at = COALESCE(users.phone_verified_at, now())
        """), {"p": phone, "e": email_for(phone), "n": name, "h": _password_hash()})
        return (await s.execute(text("SELECT email FROM users WHERE phone = :p"), {"p": phone})).scalar_one()


async def skip_cooldown(destination: str) -> None:
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE otp_codes SET created_at = created_at - interval '2 minutes' "
                             "WHERE destination = :p"), {"p": destination})


async def password_login(client: AsyncClient, tenant: SeededTenant, email: str, password: str = PASSWORD,
                         device: str = "device-0001") -> Response:
    return await client.post("/api/v1/auth/login", json={"email": email, "password": password, "device_id": device},
                             headers={"host": tenant.host})


async def login(client: AsyncClient, sms: FakeSms, tenant: SeededTenant, phone: str,
                device: str = "device-0001") -> dict[str, str]:
    """Signs in the account for `phone` with its password, passing the new-device SMS check."""
    email = await ensure_account(phone)
    await skip_cooldown(phone)
    resp = await password_login(client, tenant, email, device=device)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    if body["status"] == "device_check":
        resp = await client.post("/api/v1/auth/device/verify", json={
            "challenge": body["device_check"]["challenge"], "code": sms.last_code(phone), "device_id": device,
        }, headers={"host": tenant.host})
        assert resp.status_code == 200, resp.text
        return resp.json()
    return body["tokens"]


async def me(client: AsyncClient, tenant: SeededTenant, access: str) -> Response:
    return await client.get("/api/v1/auth/me",
                            headers={"host": tenant.host, "authorization": f"Bearer {access}"})


async def refresh(client: AsyncClient, tenant: SeededTenant, token: str) -> Response:
    return await client.post("/api/v1/auth/refresh", json={"refresh_token": token},
                             headers={"host": tenant.host})


def error_code(resp: Response) -> str:
    return resp.json()["error"]["code"]



async def auth_headers(client: AsyncClient, sms: FakeSms, tenant: SeededTenant, phone: str) -> dict[str, str]:
    """Sign in and return headers for authenticated calls on the tenant's host."""
    tokens = await login(client, sms, tenant, phone)
    return {"host": tenant.host, "authorization": f"Bearer {tokens['access_token']}"}
