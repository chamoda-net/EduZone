"""Tenant context and the per-request tenant transaction.

The tenant of a request comes from the `{tenant_slug}` path parameter when the route has one
(`/teach/{tenant_slug}/...`, migration phase 3), else from the host (`<slug>.<base>`, kept for
company sites). Tenant-facing routes depend on `TenantSession` (or `CurrentTenant` when they
need no database). Platform admin and webhook routes depend on neither. The student area
(`/learn`) uses `user_transaction()` for the user's own rows and opens the tenant of each class
it touches.
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


def _slug_of(request: Request) -> str | None:
    path_slug = request.path_params.get("tenant_slug")
    if path_slug is not None:
        return path_slug if _SLUG_RE.fullmatch(path_slug) else None
    return parse_slug(request_host(request), get_settings().base_domain)


async def optional_tenant(request: Request) -> TenantContext | None:
    """The tenant of this request, or None (main host, unknown or inactive tenant)."""
    slug = _slug_of(request)
    return await _resolve(slug) if slug else None


def is_main_host(host: str) -> bool:
    return host.strip().lower().rsplit(":", 1)[0] == get_settings().base_domain.lower()


async def site_url(request: Request) -> str:
    """Base URL for links we email: the host must be the main site or an active tenant's site,
    so a forged Host header can never put someone else's domain into our emails."""
    host = request_host(request)
    if not is_main_host(host) and await optional_tenant(request) is None:
        raise ApiError("TENANT_NOT_FOUND", "This organization does not exist.", status_code=404)
    return f"{get_settings().site_scheme}://{host}"


SiteUrl = Annotated[str, Depends(site_url)]


async def current_tenant(request: Request) -> TenantContext:
    slug = _slug_of(request)
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


@asynccontextmanager
async def user_transaction(user_id: UUID) -> AsyncIterator[AsyncSession]:
    """A read transaction scoped to one user across tenants: no app.tenant_id, only app.user_id,
    so the user-scoped RLS policies (migration 0006) show that user's own rows and nothing else."""
    async with AppSession() as session, session.begin():
        await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id)})
        yield session


CurrentTenant = Annotated[TenantContext, Depends(current_tenant)]
OptionalTenant = Annotated[TenantContext | None, Depends(optional_tenant)]


async def _tenant_session(tenant: CurrentTenant) -> AsyncIterator[AsyncSession]:
    async with tenant_transaction(tenant.id) as session:
        yield session


# scope="function": commit (or roll back) before the response is sent, so a client
# never sees success for a write that then fails to commit.
TenantSession = Annotated[AsyncSession, Depends(_tenant_session, scope="function")]
