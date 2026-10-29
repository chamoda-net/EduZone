"""Tests run against a real PostgreSQL with migrations applied (alembic upgrade head).
Connection URLs and secrets come from .env / the environment.

Seed data is written through the admin role and removed after each test, using
per-run slugs and random phone numbers so tests never collide with each other or
with dev data.
"""

import secrets
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import AdminSession
from app.integrations.sms import get_sms_sender
from app.main import app


def random_phone() -> str:
    return f"+9470{secrets.randbelow(10**7):07d}"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # A fresh client IP per test keeps per-IP OTP limits from spilling across tests.
    ip = f"10.{secrets.randbelow(256)}.{secrets.randbelow(256)}.{secrets.randbelow(254) + 1}"
    transport = ASGITransport(app=app, client=(ip, 40000))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@dataclass
class FakeSms:
    sent: list[tuple[str, str]] = field(default_factory=list)

    async def send(self, phone: str, message: str) -> None:
        self.sent.append((phone, message))

    def last_code(self, phone: str) -> str:
        message = next(m for p, m in reversed(self.sent) if p == phone)
        return message.split()[0]


@pytest.fixture
def sms() -> Iterator[FakeSms]:
    fake = FakeSms()
    app.dependency_overrides[get_sms_sender] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_sms_sender, None)


@pytest.fixture
async def phones() -> AsyncIterator[Callable[[], str]]:
    """Factory for fresh phone numbers; users and OTP rows for them are removed afterwards."""
    made: list[str] = []

    def make() -> str:
        made.append(random_phone())
        return made[-1]

    yield make
    async with AdminSession() as s, s.begin():
        await s.execute(text("DELETE FROM otp_codes WHERE destination = ANY(:p)"), {"p": made})
        await s.execute(text("DELETE FROM users WHERE phone = ANY(:p)"), {"p": made})


@dataclass(frozen=True)
class SeededTenant:
    id: UUID
    slug: str
    name: str
    host: str
    member_id: UUID      # a teacher
    teacher_phone: str
    class_id: UUID


@dataclass(frozen=True)
class Seed:
    a: SeededTenant          # active
    b: SeededTenant          # active
    suspended: SeededTenant  # status = 'suspended'


_NON_CASCADING = ("audit_logs", "access_grants", "lesson_resources")


@pytest.fixture
async def seed(phones: Callable[[], str]) -> AsyncIterator[Seed]:
    # Depends on `phones` so its user cleanup runs after the tenants are gone.
    run = uuid4().hex[:8]
    base = get_settings().base_domain
    tenants: dict[str, SeededTenant] = {}

    async with AdminSession() as s, s.begin():
        for key, status in (("a", "active"), ("b", "active"), ("suspended", "suspended")):
            slug, name, phone = f"t-{run}-{key[0]}", f"Tenant {key.upper()} {run}", phones()
            tenant_id = (await s.execute(
                text("INSERT INTO tenants (name, slug, status) VALUES (:n, :s, :st) RETURNING id"),
                {"n": name, "s": slug, "st": status},
            )).scalar_one()
            user_id = (await s.execute(
                text("INSERT INTO users (phone, full_name) VALUES (:p, :n) RETURNING id"),
                {"p": phone, "n": f"Teacher {key}"},
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
            tenants[key] = SeededTenant(tenant_id, slug, name, f"{slug}.{base}", member_id, phone, class_id)

    try:
        yield Seed(**tenants)
    finally:
        ids = [t.id for t in tenants.values()]
        async with AdminSession() as s, s.begin():
            # Tables whose rows don't cascade from a tenant delete, children first.
            for table in _NON_CASCADING:
                await s.execute(text(f"DELETE FROM {table} WHERE tenant_id = ANY(:ids)"), {"ids": ids})
            await s.execute(text("DELETE FROM tenants WHERE id = ANY(:ids)"), {"ids": ids})


AddMember = Callable[..., Awaitable[str]]


@pytest.fixture
async def members(phones: Callable[[], str]) -> AddMember:
    """Factory: add a member with a role to a seeded tenant; returns their phone."""

    async def add(tenant: SeededTenant, role: str, status: str = "active") -> str:
        phone = phones()
        async with AdminSession() as s, s.begin():
            user_id = (await s.execute(
                text("INSERT INTO users (phone, full_name) VALUES (:p, :n) RETURNING id"),
                {"p": phone, "n": f"{role.title()} {phone[-4:]}"},
            )).scalar_one()
            await s.execute(
                text("INSERT INTO tenant_members (tenant_id, user_id, role, status) VALUES (:t, :u, :r, :st)"),
                {"t": tenant.id, "u": user_id, "r": role, "st": status},
            )
        return phone

    return add
