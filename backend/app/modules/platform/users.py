"""Users and devices (migration phase 8): find an account, see where it is signed in and which devices it trusts,
end its sessions or forget a device. Support uses this when a student loses a phone or shares an account.
Accounts are platform-level, so these audit rows carry no tenant."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.auth.phone import normalize_phone
from app.modules.platform.auth import PlatformActor
from app.modules.platform.schemas import (
    SignedOut,
    UserDetail,
    UserDevice,
    UserMembership,
    UserRow,
    UserSession,
)
from app.modules.platform.service import _audit

# Ended by EduZone staff; the device then sees the ordinary "signed out" screen.
REVOKED_BY_ADMIN = "platform_admin"

_ROW = """
    SELECT u.id, u.full_name, u.email::text AS email, u.phone, u.email_verified_at IS NOT NULL AS email_verified,
           u.phone_verified_at IS NOT NULL AS phone_verified, u.is_platform_admin, u.last_login_at, u.created_at,
           u.password_hash IS NOT NULL AS has_password, u.exam, u.exam_year, u.school,
           EXISTS (SELECT 1 FROM user_identities i WHERE i.user_id = u.id) AS google_linked,
           (SELECT count(*) FROM tenant_members m WHERE m.user_id = u.id) AS memberships,
           (SELECT count(*) FROM user_sessions s
            WHERE s.user_id = u.id AND s.revoked_at IS NULL AND s.expires_at > now()) AS active_sessions
    FROM users u
"""


def _pick(model: type[Any], r: Any) -> Any:
    return model.model_validate({k: getattr(r, k) for k in model.model_fields if hasattr(r, k)})


async def search_users(session: AsyncSession, q: str) -> list[UserRow]:
    """By email, phone (any local form) or part of the name. At most 50, newest first."""
    q = q.strip()
    if len(q) < 2:
        return []
    try:
        phone = normalize_phone(q)
    except ValueError:
        phone = None
    rows = (await session.execute(text(_ROW + """
        WHERE u.email = :q OR u.phone = :phone OR u.full_name ILIKE :like OR u.email ILIKE :like
           OR (CAST(:digits AS text) <> '' AND u.phone LIKE :digits_like)
        ORDER BY (u.email = :q OR u.phone = :phone) DESC, u.created_at DESC
        LIMIT 50
    """), {"q": q, "phone": phone, "like": f"%{_escape(q)}%",
           "digits": _digits(q), "digits_like": f"%{_digits(q)}"})).all()
    return [_pick(UserRow, r) for r in rows]


def _escape(q: str) -> str:
    return q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _digits(q: str) -> str:
    """The last digits of a phone number ('0003' finds +94770000003); only for 4+ digits."""
    d = "".join(ch for ch in q if ch.isdigit())
    return d if len(d) >= 4 and len(d) == len(q.replace(" ", "")) else ""


async def get_user(session: AsyncSession, user_id: UUID) -> UserDetail:
    r = (await session.execute(text(_ROW + " WHERE u.id = :id"), {"id": user_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "User not found.", status_code=404)
    members = (await session.execute(text("""
        SELECT m.id AS member_id, m.tenant_id, t.name AS tenant_name, t.slug AS tenant_slug, m.role, m.status,
               m.joined_at
        FROM tenant_members m JOIN tenants t ON t.id = m.tenant_id
        WHERE m.user_id = :u ORDER BY (m.role <> 'student') DESC, m.joined_at DESC
    """), {"u": user_id})).all()
    sessions = (await session.execute(text("""
        (SELECT id, device_id, user_agent, host(ip_address) AS ip_address, created_at, last_seen_at, expires_at,
                revoked_at, revoke_reason, true AS active
         FROM user_sessions WHERE user_id = :u AND revoked_at IS NULL AND expires_at > now()
         ORDER BY last_seen_at DESC)
        UNION ALL
        (SELECT id, device_id, user_agent, host(ip_address), created_at, last_seen_at, expires_at,
                revoked_at, revoke_reason, false
         FROM user_sessions WHERE user_id = :u AND (revoked_at IS NOT NULL OR expires_at <= now())
         ORDER BY COALESCE(revoked_at, expires_at) DESC LIMIT 10)
    """), {"u": user_id})).all()
    devices = (await session.execute(text("""
        SELECT id, device_id, user_agent, trusted_at, last_seen_at FROM user_devices
        WHERE user_id = :u ORDER BY last_seen_at DESC
    """), {"u": user_id})).all()
    base = {k: getattr(r, k) for k in UserDetail.model_fields if hasattr(r, k)}
    return UserDetail(**base, member_of=[_pick(UserMembership, m) for m in members],
                      sessions=[_pick(UserSession, s) for s in sessions],
                      devices=[_pick(UserDevice, d) for d in devices])


async def _exists(session: AsyncSession, user_id: UUID) -> None:
    if (await session.execute(text("SELECT 1 FROM users WHERE id = :id"), {"id": user_id})).first() is None:
        raise ApiError("NOT_FOUND", "User not found.", status_code=404)


async def sign_out_everywhere(session: AsyncSession, actor: PlatformActor, user_id: UUID) -> SignedOut:
    await _exists(session, user_id)
    ended = (await session.execute(text("""
        UPDATE user_sessions SET revoked_at = now(), revoke_reason = :r
        WHERE user_id = :u AND revoked_at IS NULL AND expires_at > now()
    """), {"u": user_id, "r": REVOKED_BY_ADMIN})).rowcount
    await _audit(session, actor, "platform.user.sign_out", "user", user_id, {"sessions_ended": ended})
    return SignedOut(sessions_ended=ended)


async def forget_device(session: AsyncSession, actor: PlatformActor, user_id: UUID, device_row_id: UUID) -> SignedOut:
    """The device is no longer trusted (signing in there asks for an SMS code again) and its sessions end."""
    d = (await session.execute(text("DELETE FROM user_devices WHERE id = :id AND user_id = :u RETURNING device_id"),
                               {"id": device_row_id, "u": user_id})).one_or_none()
    if d is None:
        raise ApiError("NOT_FOUND", "Device not found.", status_code=404)
    ended = (await session.execute(text("""
        UPDATE user_sessions SET revoked_at = now(), revoke_reason = :r
        WHERE user_id = :u AND device_id = :d AND revoked_at IS NULL AND expires_at > now()
    """), {"u": user_id, "d": d.device_id, "r": REVOKED_BY_ADMIN})).rowcount
    await _audit(session, actor, "platform.user.forget_device", "user", user_id,
                 {"device_id": d.device_id, "sessions_ended": ended})
    return SignedOut(sessions_ended=ended)
