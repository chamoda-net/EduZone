"""Tests run against a real PostgreSQL with migrations applied (alembic upgrade head).
Connection URLs and secrets come from .env / the environment.

Seed data is written through the admin role and removed after each test, using
per-run slugs and random phone numbers so tests never collide with each other or
with dev data.
"""

import hashlib
import json
import secrets
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from app.core.config import BunnyLibraryKeys, get_settings
from app.core.db import AdminSession
from app.integrations.bunny import bunny_http
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


_TENANT_TABLES: list[str] = []


def purge_tenants(ids: list[UUID]) -> None:
    """Remove test tenants and everything under them.

    The ledger is append-only (triggers block DELETE even for the admin role), so this runs
    as the schema owner with triggers paused. Test databases only.
    """
    url = get_settings().migration_database_url.replace("postgresql+psycopg", "postgresql")
    with psycopg.connect(url) as conn:
        conn.execute("SET session_replication_role = replica")   # skip triggers and FK checks
        if not _TENANT_TABLES:
            _TENANT_TABLES.extend(r[0] for r in conn.execute("""
                SELECT c.relname FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
                WHERE n.nspname = 'public' AND c.relkind = 'r'
            """))
        for table in _TENANT_TABLES:
            conn.execute(f"DELETE FROM {table} WHERE tenant_id = ANY(%s)", (ids,))  # type: ignore[arg-type]
        conn.execute("DELETE FROM tenants WHERE id = ANY(%s)", (ids,))


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
        purge_tenants([t.id for t in tenants.values()])


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


# --- fake Bunny (no network, no account) -----------------------------------------

@dataclass
class FakeBunny:
    videos: dict[str, dict[str, Any]] = field(default_factory=dict)
    files: dict[str, bytes] = field(default_factory=dict)
    calls: list[tuple[str, str]] = field(default_factory=list)
    down: bool = False
    library_id: int = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.calls.append((request.method, request.url.path))
        if self.down:
            return httpx.Response(503)
        path = request.url.path
        if request.url.host == "video.bunnycdn.com":
            assert request.headers["AccessKey"].startswith("stream-key-")
            parts = path.strip("/").split("/")          # library/<id>/videos[/<guid>]
            if request.method == "POST" and len(parts) == 3:
                guid = str(uuid.uuid4())
                self.videos[guid] = {"guid": guid, "title": json.loads(request.content)["title"], "status": 0}
                return httpx.Response(200, json=self.videos[guid])
            guid = parts[3]
            if guid not in self.videos:
                return httpx.Response(404)
            if request.method == "GET":
                return httpx.Response(200, json=self.videos[guid])
            if request.method == "DELETE":
                del self.videos[guid]
                return httpx.Response(200, json={"success": True})
        if request.url.host == "storage.bunnycdn.com":
            assert request.headers["AccessKey"] == "storage-key"
            key = path.split("/", 2)[2]                    # /<zone>/<path>
            if request.method == "PUT":
                assert request.headers["Checksum"] == hashlib.sha256(request.content).hexdigest().upper()
                self.files[key] = request.content
                return httpx.Response(201)
            if request.method == "DELETE":
                self.files.pop(key, None)
                return httpx.Response(200)
        return httpx.Response(404)


@pytest.fixture
async def bunny(seed: Seed) -> AsyncIterator[FakeBunny]:
    """Fake Bunny, Bunny settings for the test, and a video library for tenant A."""
    fake = FakeBunny()
    library_id = secrets.randbelow(10**9) + 10**9
    settings = get_settings()
    saved = {k: getattr(settings, k) for k in (
        "bunny_stream_libraries", "bunny_webhook_token", "bunny_storage_zone", "bunny_storage_api_key",
        "bunny_cdn_host", "bunny_cdn_token_key", "bunny_storage_host")}
    settings.bunny_stream_libraries = {str(library_id): BunnyLibraryKeys(api_key=f"stream-key-{library_id}",
                                                                          token_key="embed-token-key")}
    settings.bunny_webhook_token = "hook-secret"
    settings.bunny_storage_zone, settings.bunny_storage_api_key = "eduzone-files", "storage-key"
    settings.bunny_storage_host = "storage.bunnycdn.com"
    settings.bunny_cdn_host, settings.bunny_cdn_token_key = "files.example.b-cdn.net", "cdn-token-key"
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE tenants SET bunny_library_id = :lib WHERE id = :t"),
                        {"lib": library_id, "t": seed.a.id})
    fake.library_id = library_id

    http = httpx.AsyncClient(transport=httpx.MockTransport(fake.handler))
    app.dependency_overrides[bunny_http] = lambda: http
    yield fake
    app.dependency_overrides.pop(bunny_http, None)
    await http.aclose()
    for k, v in saved.items():
        setattr(settings, k, v)


