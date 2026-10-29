"""Tenant context: Host header -> tenant, and the per-request tenant transaction.

Tenant-facing routes depend on `TenantSession` (or `CurrentTenant` when they need no
database). Platform admin and webhook routes depend on neither.
"""

import re
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError

# Same rule as the CHECK on tenants.slug.
_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$")


@dataclass(frozen=True, slots=True)
class TenantContext:
    id: UUID
    slug: str


def parse_slug(host: str, base_domain: str) -> str | None:
    """'physics.eduzone.lk:443' -> 'physics'. Anything else (bare domain, nested
    subdomains, foreign hosts, malformed slugs) -> None."""
    hostname = host.strip().lower().rsplit(":", 1)[0] if host else ""
    suffix = "." + base_domain.lower()
    if not hostname.endswith(suffix):
        return None
    slug = hostname[: -len(suffix)]
    return slug if _SLUG_RE.fullmatch(slug) else None


def request_host(request: Request) -> str:
    """The host the user is on. X-Forwarded-Host (set by the frontend server or a reverse
    proxy, which can't override Host) wins over Host.

    Not a trust boundary: any client can already send whatever Host it likes. Tenant
    access is enforced by RLS and by the tenant id inside each access token.
    """
    forwarded = request.headers.get("x-forwarded-host", "").split(",")[0].strip()
    return forwarded or request.headers.get("host", "")


async def _resolve(slug: str) -> TenantContext | None:
    # resolve_tenant() is SECURITY DEFINER: RLS hides `tenants` until the tenant is known.
    async with AppSession() as session:
        row = (
            await session.execute(text("SELECT id, status FROM resolve_tenant(:slug)"), {"slug": slug})
        ).one_or_none()
    if row is None or row.status != "active":
        return None
    return TenantContext(id=row.id, slug=slug)


async def current_tenant(request: Request) -> TenantContext:
    slug = parse_slug(request_host(request), get_settings().base_domain)
    tenant = await _resolve(slug) if slug else None
    if tenant is None:
        raise ApiError("TENANT_NOT_FOUND", "This organization does not exist.", status_code=404)
    return tenant


@asynccontextmanager
async def tenant_transaction(tenant_id: UUID) -> AsyncIterator[AsyncSession]:
    """One transaction bound to one tenant. Commits on success, rolls back on error.

    set_config(..., true) is SET LOCAL: it ends with the transaction, so a pooled
    connection never carries a tenant into the next request.
    """
    async with AppSession() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.tenant_id', :tid, true)"), {"tid": str(tenant_id)}
        )
        yield session


CurrentTenant = Annotated[TenantContext, Depends(current_tenant)]


async def _tenant_session(tenant: CurrentTenant) -> AsyncIterator[AsyncSession]:
    async with tenant_transaction(tenant.id) as session:
        yield session


# scope="function": commit (or roll back) before the response is sent, so a client
# never sees success for a write that then fails to commit.
TenantSession = Annotated[AsyncSession, Depends(_tenant_session, scope="function")]
