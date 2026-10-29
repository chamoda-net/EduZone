"""Tests run against a real PostgreSQL with migrations applied (alembic upgrade head).
Connection URLs come from .env / the environment.

Seed data is written through the admin role and removed after each test, using
per-run slugs so tests never collide with each other or with dev data.
"""

import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import AdminSession
from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@dataclass(frozen=True)
class SeededTenant:
    id: UUID
    slug: str
    name: str
    host: str
    member_id: UUID
    class_id: UUID


@dataclass(frozen=True)
class Seed:
    a: SeededTenant          # active
    b: SeededTenant          # active
    suspended: SeededTenant  # status = 'suspended'


@pytest.fixture
async def seed() -> AsyncIterator[Seed]:
    run = uuid4().hex[:8]
    base = get_settings().base_domain
    tenants: dict[str, SeededTenant] = {}
    user_ids: list[UUID] = []

    async with AdminSession() as s, s.begin():
        for key, status in (("a", "active"), ("b", "active"), ("suspended", "suspended")):
            slug, name = f"t-{run}-{key[0]}", f"Tenant {key.upper()} {run}"
            tenant_id = (await s.execute(
                text("INSERT INTO tenants (name, slug, status) VALUES (:n, :s, :st) RETURNING id"),
                {"n": name, "s": slug, "st": status},
            )).scalar_one()
            user_id = (await s.execute(
                text("INSERT INTO users (phone, full_name) VALUES (:p, :n) RETURNING id"),
                {"p": f"+9470{secrets.randbelow(10**7):07d}", "n": f"Teacher {key}"},
            )).scalar_one()
            member_id = (await s.execute(
                text("INSERT INTO tenant_members (tenant_id, user_id, role) "
                     "VALUES (:t, :u, 'teacher') RETURNING id"),
                {"t": tenant_id, "u": user_id},
            )).scalar_one()
            class_id = (await s.execute(
                text("INSERT INTO classes (tenant_id, teacher_member_id, title, slug, pricing_model) "
                     "VALUES (:t, :m, :title, 'physics', 'free') RETURNING id"),
                {"t": tenant_id, "m": member_id, "title": f"Physics {key}"},
            )).scalar_one()
            user_ids.append(user_id)
            tenants[key] = SeededTenant(tenant_id, slug, name, f"{slug}.{base}", member_id, class_id)

    try:
        yield Seed(**tenants)
    finally:
        async with AdminSession() as s, s.begin():
            await s.execute(text("DELETE FROM tenants WHERE id = ANY(:ids)"),
                            {"ids": [t.id for t in tenants.values()]})
            await s.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": user_ids})
