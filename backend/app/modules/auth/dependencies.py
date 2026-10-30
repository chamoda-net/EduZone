from dataclasses import dataclass, replace
from ipaddress import ip_address
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.tenancy import TenantSession
from app.modules.auth import repository as repo
from app.modules.auth.tokens import decode_access_token

# auto_error=False: missing or malformed headers reach us as None and get our error shape.
# Declaring the scheme also gives the API docs an "Authorize" button.
_bearer = HTTPBearer(auto_error=False, description="Access token from /auth/login, /auth/register or /auth/refresh")

SIGNED_IN_ELSEWHERE = "signed_in_on_another_device"


@dataclass(frozen=True, slots=True)
class UserContext:
    """A signed-in account (global, not tied to a tenant)."""

    user_id: UUID
    session_id: UUID


def session_ended(reason: str | None) -> ApiError:
    if reason == SIGNED_IN_ELSEWHERE:
        return ApiError("SIGNED_IN_ELSEWHERE", "You were signed out because your account was used on another device.", 401)
    return ApiError("SESSION_REVOKED", "You were signed out. Please sign in again.", 401)


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UserContext:
    if credentials is None:
        raise ApiError("UNAUTHORIZED", "Please sign in.", status_code=401)
    claims = decode_access_token(credentials.credentials)
    # Checked on every request so the one-device rule and sign-outs apply immediately.
    async with AppSession() as session:
        state = await repo.session_state(session, claims.session_id, claims.user_id)
    if state is None or state.expired:
        raise session_ended(None)
    if state.revoked:
        raise session_ended(state.revoke_reason)
    return UserContext(claims.user_id, claims.session_id)


CurrentUser = Annotated[UserContext, Depends(current_user)]


@dataclass(frozen=True, slots=True)
class AuthContext:
    """A signed-in account on a tenant. `member_id`/`role` come from the member row for this
    tenant (looked up on every request, so role changes and suspensions apply at once) and are
    None until the student joins or pays for something here (CLAUDE.md section 2)."""

    user_id: UUID
    member_id: UUID | None
    role: str | None
    session_id: UUID


async def current_member(user: CurrentUser, session: TenantSession) -> AuthContext:
    member = await repo.get_member(session, user.user_id)
    if member is not None and member.status == "suspended":
        raise ApiError("ACCOUNT_SUSPENDED", "Your account has been suspended here. Contact your teacher.", 403)
    if member is None or member.status != "active":
        return AuthContext(user.user_id, member.id if member else None, None, user.session_id)
    return AuthContext(user.user_id, member.id, member.role, user.session_id)


CurrentMember = Annotated[AuthContext, Depends(current_member, scope="function")]


async def ensure_student_member(session: AsyncSession, auth: AuthContext) -> AuthContext:
    """Joining or paying makes the user a member of this tenant (a student) if they aren't yet.
    Runs in the request's tenant transaction."""
    if auth.member_id is not None and auth.role is not None:
        return auth
    member = await repo.upsert_student_member(session, auth.user_id)
    if member.status != "active":
        raise ApiError("ACCOUNT_SUSPENDED", "Your account has been suspended here. Contact your teacher.", 403)
    return replace(auth, member_id=member.id, role=member.role)


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
class StaffAuth:
    """AuthContext for a staff member: membership is guaranteed."""

    user_id: UUID
    member_id: UUID
    role: str
    session_id: UUID


@dataclass(frozen=True, slots=True)
class Actor:
    """A signed-in staff member making a change (for permission checks and audit rows)."""

    auth: StaffAuth
    ip: str | None

    @property
    def manages_all(self) -> bool:
        # Owners and admins manage every class; teachers only the classes they teach.
        return self.auth.role in ("owner", "admin")


async def staff_actor(request: Request, auth: CurrentMember) -> Actor:
    if auth.member_id is None or auth.role not in STAFF_ROLES:
        raise ApiError("ACCESS_DENIED", "Only organization staff can do this.", status_code=403)
    return Actor(StaffAuth(auth.user_id, auth.member_id, auth.role, auth.session_id), client_ip(request))


StaffActor = Annotated[Actor, Depends(staff_actor, scope="function")]
