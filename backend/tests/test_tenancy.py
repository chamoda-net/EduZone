"""Tenant resolution (Host -> tenant) and the tenant transaction."""

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.db import AppSession, app_engine
from app.core.tenancy import parse_slug, tenant_transaction
from tests.conftest import Seed


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("physics.eduzone.lk", "physics"),
        ("Physics.EduZone.lk", "physics"),
        ("physics.eduzone.lk:8443", "physics"),
        ("al-physics-2027.eduzone.lk", "al-physics-2027"),
        ("eduzone.lk", None),                       # bare domain
        ("a.b.eduzone.lk", None),                   # nested subdomain
        ("physics.eduzone.lk.evil.com", None),      # suffix trick
        ("physicseduzone.lk", None),                # no dot before the base domain
        ("-bad.eduzone.lk", None),                  # fails the slug rule
        ("x.eduzone.lk", None),                     # too short for the slug rule
        ("", None),
    ],
)
def test_parse_slug(host: str, expected: str | None) -> None:
    assert parse_slug(host, "eduzone.lk") == expected


async def test_each_host_sees_its_own_tenant(client: AsyncClient, seed: Seed) -> None:
    for tenant in (seed.a, seed.b):
        resp = await client.get("/api/v1/public/tenant", headers={"host": tenant.host})
        assert resp.status_code == 200
        assert resp.json() == {
            "name": tenant.name, "slug": tenant.slug, "logo_url": None, "primary_color": None,
        }


async def test_forwarded_host_wins(client: AsyncClient, seed: Seed) -> None:
    # The frontend server calls the API on an internal address and passes the user's host.
    resp = await client.get("/api/v1/public/tenant",
                            headers={"host": "api.internal:8000", "x-forwarded-host": seed.b.host})
    assert resp.json()["slug"] == seed.b.slug


@pytest.mark.parametrize("host", ["nobody-here.eduzone.lk", "eduzone.lk", "localhost", "evil.com"])
async def test_unknown_host_is_404(client: AsyncClient, seed: Seed, host: str) -> None:
    resp = await client.get("/api/v1/public/tenant", headers={"host": host})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"


async def test_suspended_tenant_is_404(client: AsyncClient, seed: Seed) -> None:
    resp = await client.get("/api/v1/public/tenant", headers={"host": seed.suspended.host})
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "TENANT_NOT_FOUND"


async def test_health_needs_no_tenant(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/health", headers={"host": "api.example.com"})
    assert resp.status_code == 200


async def test_tenant_context_does_not_outlive_the_transaction() -> None:
    # One physical connection, two transactions: SET LOCAL must not leak into the second.
    async with app_engine.connect() as conn:
        async with conn.begin():
            await conn.execute(text("SELECT set_config('app.tenant_id', gen_random_uuid()::text, true)"))
        async with conn.begin():
            leaked = (await conn.execute(text("SELECT current_tenant_id()"))).scalar_one()
    assert leaked is None


async def test_tenant_transaction_rolls_back_on_error(seed: Seed) -> None:
    with pytest.raises(RuntimeError):
        async with tenant_transaction(seed.a.id) as session:
            await session.execute(
                text("UPDATE classes SET title = 'changed' WHERE id = :id"), {"id": seed.a.class_id}
            )
            raise RuntimeError("boom")
    async with tenant_transaction(seed.a.id) as session:
        title = (await session.execute(
            text("SELECT title FROM classes WHERE id = :id"), {"id": seed.a.class_id}
        )).scalar_one()
    assert title == "Physics a"


async def test_resolve_tenant_hides_everything_but_id_and_status(seed: Seed) -> None:
    async with AppSession() as session:
        cols = (await session.execute(text("SELECT * FROM resolve_tenant(:s)"), {"s": seed.a.slug})).keys()
    assert list(cols) == ["id", "status"]


async def test_no_context_means_no_rows(seed: Seed) -> None:
    async with AppSession() as session:
        count = (await session.execute(text("SELECT count(*) FROM classes"))).scalar_one()
    assert count == 0


async def test_write_into_other_tenant_is_rejected(seed: Seed) -> None:
    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_transaction(seed.a.id) as session:
            await session.execute(
                text("INSERT INTO classes (tenant_id, teacher_member_id, title, slug, pricing_model) "
                     "VALUES (:t, :m, 'x', 'sneaky', 'free')"),
                {"t": seed.b.id, "m": seed.b.member_id},
            )
