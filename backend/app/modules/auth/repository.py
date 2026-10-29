from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# --- OTP (platform-level table; any session) ------------------------------------


async def lock_phone(session: AsyncSession, phone: str) -> None:
    """Serialise OTP work per phone number for the rest of the transaction."""
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('otp:' || :p))"), {"p": phone})


async def otp_request_stats(
    session: AsyncSession, phone: str, ip: str | None, cooldown_seconds: int
) -> Any:
    return (await session.execute(text("""
        SELECT
          EXISTS (SELECT 1 FROM otp_codes
                  WHERE destination = :p AND purpose = 'login'
                    AND created_at > now() - make_interval(secs => CAST(:cooldown AS integer))) AS in_cooldown,
          (SELECT count(*) FROM otp_codes
           WHERE destination = :p AND purpose = 'login'
             AND created_at > now() - interval '1 hour')                      AS phone_last_hour,
          (SELECT count(*) FROM otp_codes
           WHERE CAST(:ip AS inet) IS NOT NULL AND request_ip = CAST(:ip AS inet)
             AND created_at > now() - interval '1 hour')                      AS ip_last_hour
    """), {"p": phone, "ip": ip, "cooldown": cooldown_seconds})).one()


async def insert_otp(
    session: AsyncSession, phone: str, code_hash: str, ttl_seconds: int, ip: str | None
) -> None:
    await session.execute(text("""
        INSERT INTO otp_codes (destination, purpose, code_hash, expires_at, request_ip)
        VALUES (:p, 'login', :h, now() + make_interval(secs => CAST(:ttl AS integer)), CAST(:ip AS inet))
    """), {"p": phone, "h": code_hash, "ttl": ttl_seconds, "ip": ip})


async def latest_otp_for_update(session: AsyncSession, phone: str) -> Any:
    return (await session.execute(text("""
        SELECT id, code_hash, attempts, consumed_at IS NOT NULL AS consumed, expires_at <= now() AS expired
        FROM otp_codes
        WHERE destination = :p AND purpose = 'login'
        ORDER BY created_at DESC
        LIMIT 1
        FOR UPDATE
    """), {"p": phone})).one_or_none()


async def increment_otp_attempts(session: AsyncSession, otp_id: UUID) -> None:
    await session.execute(text("UPDATE otp_codes SET attempts = attempts + 1 WHERE id = :id"), {"id": otp_id})


async def consume_otp(session: AsyncSession, otp_id: UUID) -> None:
    await session.execute(text("UPDATE otp_codes SET consumed_at = now() WHERE id = :id"), {"id": otp_id})


# --- Users (global) -------------------------------------------------------------


async def get_user_by_phone(session: AsyncSession, phone: str) -> Any:
    return (await session.execute(
        text("SELECT id, full_name, preferred_language FROM users WHERE phone = :p"), {"p": phone}
    )).one_or_none()


async def upsert_user_on_login(session: AsyncSession, phone: str, full_name: str | None) -> UUID:
    """Existing user: record the login (their name is never overwritten). New user: create
    them with full_name, which the caller has already required.

    Not a single INSERT ... ON CONFLICT: Postgres checks NOT NULL on full_name before it
    detects the conflict, so an existing user signing in without a name would fail.
    """
    existing = (await session.execute(text("""
        UPDATE users SET last_login_at = now(), phone_verified_at = COALESCE(phone_verified_at, now())
        WHERE phone = :p
        RETURNING id
    """), {"p": phone})).scalar_one_or_none()
    if existing is not None:
        return existing
    if full_name is None:
        raise ValueError("full_name is required to create a user")
    return (await session.execute(text("""
        INSERT INTO users (phone, full_name, phone_verified_at, last_login_at)
        VALUES (:p, :n, now(), now())
        ON CONFLICT (phone) DO UPDATE SET last_login_at = now()   -- lost a race with a parallel signup
        RETURNING id
    """), {"p": phone, "n": full_name})).scalar_one()


# --- Membership and sessions (tenant transaction; RLS scopes every query) --------


async def get_member(session: AsyncSession, user_id: UUID) -> Any:
    return (await session.execute(
        text("SELECT id, role, status FROM tenant_members WHERE user_id = :u"), {"u": user_id}
    )).one_or_none()


async def insert_student_member(session: AsyncSession, user_id: UUID) -> UUID:
    return (await session.execute(text("""
        INSERT INTO tenant_members (tenant_id, user_id, role)
        VALUES (current_tenant_id(), :u, 'student')
        RETURNING id
    """), {"u": user_id})).scalar_one()


async def activate_member(session: AsyncSession, member_id: UUID) -> None:
    await session.execute(
        text("UPDATE tenant_members SET status = 'active' WHERE id = :id"), {"id": member_id}
    )


async def revoke_user_sessions(session: AsyncSession, user_id: UUID, reason: str) -> None:
    await session.execute(text("""
        UPDATE user_sessions SET revoked_at = now(), revoke_reason = :r
        WHERE user_id = :u AND revoked_at IS NULL
    """), {"u": user_id, "r": reason})


async def insert_session(
    session: AsyncSession, user_id: UUID, device_id: str, refresh_hash: str, ttl_days: int,
    ip: str | None, user_agent: str | None,
) -> UUID:
    return (await session.execute(text("""
        INSERT INTO user_sessions
            (tenant_id, user_id, device_id, refresh_token_hash, ip_address, user_agent, expires_at)
        VALUES (current_tenant_id(), :u, :d, :h, CAST(:ip AS inet), :ua, now() + make_interval(days => :ttl))
        RETURNING id
    """), {"u": user_id, "d": device_id, "h": refresh_hash, "ip": ip, "ua": user_agent,
           "ttl": ttl_days})).scalar_one()


async def session_by_refresh_hash_for_update(session: AsyncSession, refresh_hash: str) -> Any:
    return (await session.execute(text("""
        SELECT s.id, s.user_id, s.revoked_at IS NOT NULL AS revoked, s.expires_at <= now() AS expired,
               m.id AS member_id, m.role, m.status AS member_status
        FROM user_sessions s
        JOIN tenant_members m ON m.tenant_id = s.tenant_id AND m.user_id = s.user_id
        WHERE s.refresh_token_hash = :h
        FOR UPDATE OF s
    """), {"h": refresh_hash})).one_or_none()


async def rotate_session(
    session: AsyncSession, session_id: UUID, refresh_hash: str, ttl_days: int,
    ip: str | None, user_agent: str | None,
) -> None:
    await session.execute(text("""
        UPDATE user_sessions
           SET refresh_token_hash = :h, last_seen_at = now(),
               expires_at = now() + make_interval(days => :ttl),
               ip_address = CAST(:ip AS inet), user_agent = :ua
        WHERE id = :id
    """), {"id": session_id, "h": refresh_hash, "ttl": ttl_days, "ip": ip, "ua": user_agent})


async def revoke_session(session: AsyncSession, session_id: UUID, reason: str) -> None:
    await session.execute(text("""
        UPDATE user_sessions SET revoked_at = now(), revoke_reason = :r
        WHERE id = :id AND revoked_at IS NULL
    """), {"id": session_id, "r": reason})


async def get_auth_state(session: AsyncSession, session_id: UUID, user_id: UUID) -> Any:
    return (await session.execute(text("""
        SELECT s.revoked_at IS NOT NULL AS revoked, s.expires_at <= now() AS expired,
               m.id AS member_id, m.role, m.status AS member_status
        FROM user_sessions s
        JOIN tenant_members m ON m.tenant_id = s.tenant_id AND m.user_id = s.user_id
        WHERE s.id = :sid AND s.user_id = :uid
    """), {"sid": session_id, "uid": user_id})).one_or_none()


async def get_me(session: AsyncSession, user_id: UUID) -> Any:
    return (await session.execute(text("""
        SELECT u.id AS user_id, m.id AS member_id, u.full_name, u.phone, m.role, u.preferred_language
        FROM users u JOIN tenant_members m ON m.user_id = u.id
        WHERE u.id = :u
    """), {"u": user_id})).one()
