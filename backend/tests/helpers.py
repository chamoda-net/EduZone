"""Shared HTTP helpers for tests."""

from collections.abc import Callable

from httpx import AsyncClient, Response
from sqlalchemy import text

from app.core.db import AdminSession
from tests.conftest import FakeSms, SeededTenant

Phones = Callable[[], str]


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



async def auth_headers(client: AsyncClient, sms: FakeSms, tenant: SeededTenant, phone: str) -> dict[str, str]:
    """Sign in and return headers for authenticated calls on the tenant's host."""
    tokens = await login(client, sms, tenant, phone)
    return {"host": tenant.host, "authorization": f"Bearer {tokens['access_token']}"}
