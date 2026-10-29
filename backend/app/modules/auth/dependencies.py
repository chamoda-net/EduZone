from dataclasses import dataclass
from ipaddress import ip_address
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request

from app.core.errors import ApiError
from app.core.tenancy import CurrentTenant, TenantSession
from app.modules.auth import repository as repo
from app.modules.auth.tokens import decode_access_token


@dataclass(frozen=True, slots=True)
class AuthContext:
    user_id: UUID
    member_id: UUID
    role: str            # from the member row, not the token, so role changes apply at once
    session_id: UUID


async def current_member(request: Request, tenant: CurrentTenant, session: TenantSession) -> AuthContext:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError("UNAUTHORIZED", "Please sign in.", status_code=401)
    claims = decode_access_token(token)
    if claims.tenant_id != tenant.id:
        # A token issued on tenant A's host is never accepted on tenant B's host.
        raise ApiError("UNAUTHORIZED", "Please sign in.", status_code=401)
    # Checked on every request so the one-device rule and suspensions apply immediately.
    state = await repo.get_auth_state(session, claims.session_id, claims.user_id)
    if state is None or state.revoked or state.expired or state.member_status != "active":
        raise ApiError("SESSION_REVOKED", "You were signed out. Please sign in again.", status_code=401)
    return AuthContext(claims.user_id, state.member_id, state.role, claims.session_id)


CurrentMember = Annotated[AuthContext, Depends(current_member, scope="function")]


def client_ip(request: Request) -> str | None:
    # Direct peer address. Behind a proxy/CDN this must read the trusted forwarded header instead.
    host = request.client.host if request.client else None
    try:
        return str(ip_address(host)) if host else None
    except ValueError:
        return None


def user_agent(request: Request) -> str | None:
    return request.headers.get("user-agent", "")[:512] or None


STAFF_ROLES = frozenset({"owner", "admin", "teacher"})


@dataclass(frozen=True, slots=True)
class Actor:
    """A signed-in staff member making a change (for permission checks and audit rows)."""

    auth: AuthContext
    ip: str | None

    @property
    def manages_all(self) -> bool:
        # Owners and admins manage every class; teachers only the classes they teach.
        return self.auth.role in ("owner", "admin")


async def staff_actor(request: Request, auth: CurrentMember) -> Actor:
    if auth.role not in STAFF_ROLES:
        raise ApiError("ACCESS_DENIED", "Only organization staff can do this.", status_code=403)
    return Actor(auth, client_ip(request))


StaffActor = Annotated[Actor, Depends(staff_actor, scope="function")]
