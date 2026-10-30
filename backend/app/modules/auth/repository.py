"""Identity data access. Users, sessions, devices and tokens are platform-level (any session);
membership queries run in a tenant transaction, where RLS scopes them to that tenant."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_USER_COLUMNS = """
    id, email, password_hash, full_name, phone, preferred_language, exam, exam_year, school,
    phone_verified_at IS NOT NULL AS phone_verified, email_verified_at IS NOT NULL AS email_verified
"""

# --- Users ------------------------------------------------------------------------------


async def get_user(session: AsyncSession, user_id: UUID) -> Any:
    return (await session.execute(text(f"SELECT {_USER_COLUMNS} FROM users WHERE id = :u"), {"u": user_id})).one()


async def get_user_by_email(session: AsyncSession, email: str, *, for_update: bool = False) -> Any:
    lock = " FOR UPDATE" if for_update else ""
    return (await session.execute(
        text(f"SELECT {_USER_COLUMNS} FROM users WHERE email = :e{lock}"), {"e": email}
    )).one_or_none()


async def lock_email(session: AsyncSession, email: str) -> None:
    """Serialise sign-up and sign-in work per email for the rest of the transaction."""
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('email:' || lower(:e)))"), {"e": email})


async def create_user(
    session: AsyncSession, *, email: str | None, password_hash: str | None, full_name: str, email_verified: bool,
) -> UUID:
    return (await session.execute(text("""
        INSERT INTO users (email, password_hash, full_name, email_verified_at, last_login_at)
        VALUES (:e, :ph, :n, CASE WHEN :ev THEN now() END, now())
        RETURNING id
    """), {"e": email, "ph": password_hash, "n": full_name, "ev": email_verified})).scalar_one()


async def set_password(session: AsyncSession, user_id: UUID, password_hash: str) -> None:
    await session.execute(text("UPDATE users SET password_hash = :h WHERE id = :u"), {"u": user_id, "h": password_hash})


async def mark_email_verified(session: AsyncSession, user_id: UUID, email: str) -> bool:
    """Only if the address is still the one that was verified (the user may have changed it)."""
    return (await session.execute(text("""
        UPDATE users SET email_verified_at = COALESCE(email_verified_at, now())
        WHERE id = :u AND email = :e RETURNING id
    """), {"u": user_id, "e": email})).first() is not None


async def touch_login(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(text("UPDATE users SET last_login_at = now() WHERE id = :u"), {"u": user_id})


async def phone_owner(session: AsyncSession, phone: str) -> UUID | None:
    return (await session.execute(text("SELECT id FROM users WHERE phone = :p"), {"p": phone})).scalar_one_or_none()


async def set_verified_phone(session: AsyncSession, user_id: UUID, phone: str) -> None:
    await session.execute(text("""
        UPDATE users SET phone = :p, phone_verified_at = now() WHERE id = :u
    """), {"u": user_id, "p": phone})


async def update_profile(session: AsyncSession, user_id: UUID, values: dict[str, Any]) -> None:
    if not values:
        return
    sets = ", ".join(f"{k} = :{k}" for k in values)  # keys come from the schema, never from input
    await session.execute(text(f"UPDATE users SET {sets} WHERE id = :u"), {**values, "u": user_id})


# --- Google identities ------------------------------------------------------------------


async def user_for_identity(session: AsyncSession, provider: str, subject: str) -> UUID | None:
    return (await session.execute(text("""
        UPDATE user_identities SET last_used_at = now()
        WHERE provider = :p AND subject = :s RETURNING user_id
    """), {"p": provider, "s": subject})).scalar_one_or_none()


async def link_identity(session: AsyncSession, user_id: UUID, provider: str, subject: str, email: str | None) -> None:
    await session.execute(text("""
        INSERT INTO user_identities (user_id, provider, subject, email) VALUES (:u, :p, :s, :e)
    """), {"u": user_id, "p": provider, "s": subject, "e": email})


# --- Devices and sessions ---------------------------------------------------------------


async def is_trusted_device(session: AsyncSession, user_id: UUID, device_id: str) -> bool:
    return (await session.execute(text("""
        UPDATE user_devices SET last_seen_at = now()
        WHERE user_id = :u AND device_id = :d RETURNING id
    """), {"u": user_id, "d": device_id})).first() is not None


async def trust_device(session: AsyncSession, user_id: UUID, device_id: str, user_agent: str | None) -> None:
    await session.execute(text("""
        INSERT INTO user_devices (user_id, device_id, user_agent) VALUES (:u, :d, :ua)
        ON CONFLICT (user_id, device_id) DO UPDATE SET last_seen_at = now(), user_agent = EXCLUDED.user_agent
    """), {"u": user_id, "d": device_id, "ua": user_agent})


async def is_staff_anywhere(session: AsyncSession, user_id: UUID) -> bool:
    return bool((await session.execute(text("SELECT user_is_staff_anywhere(:u)"), {"u": user_id})).scalar_one())


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
        INSERT INTO user_sessions (user_id, device_id, refresh_token_hash, ip_address, user_agent, expires_at)
        VALUES (:u, :d, :h, CAST(:ip AS inet), :ua, now() + make_interval(days => :ttl))
        RETURNING id
    """), {"u": user_id, "d": device_id, "h": refresh_hash, "ip": ip, "ua": user_agent,
           "ttl": ttl_days})).scalar_one()


async def session_by_refresh_hash_for_update(session: AsyncSession, refresh_hash: str) -> Any:
    return (await session.execute(text("""
        SELECT id, user_id, revoked_at IS NOT NULL AS revoked, revoke_reason, expires_at <= now() AS expired
        FROM user_sessions WHERE refresh_token_hash = :h
        FOR UPDATE
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


async def session_state(session: AsyncSession, session_id: UUID, user_id: UUID) -> Any:
    return (await session.execute(text("""
        SELECT revoked_at IS NOT NULL AS revoked, revoke_reason, expires_at <= now() AS expired
        FROM user_sessions WHERE id = :sid AND user_id = :uid
    """), {"sid": session_id, "uid": user_id})).one_or_none()


# --- Password sign-in throttling ---------------------------------------------------------


async def recent_failures(session: AsyncSession, email: str, ip: str | None, window_minutes: int) -> Any:
    return (await session.execute(text("""
        SELECT
          (SELECT count(*) FROM login_attempts WHERE email = :e AND NOT succeeded
             AND created_at > now() - make_interval(mins => :w)) AS by_email,
          (SELECT count(*) FROM login_attempts WHERE CAST(:ip AS inet) IS NOT NULL
             AND ip_address = CAST(:ip AS inet) AND NOT succeeded
             AND created_at > now() - make_interval(mins => :w)) AS by_ip
    """), {"e": email, "ip": ip, "w": window_minutes})).one()


async def record_attempt(session: AsyncSession, email: str, ip: str | None, succeeded: bool) -> None:
    await session.execute(text("""
        INSERT INTO login_attempts (email, ip_address, succeeded) VALUES (:e, CAST(:ip AS inet), :ok)
    """), {"e": email, "ip": ip, "ok": succeeded})


# --- Email verification and recovery links ----------------------------------------------


async def insert_email_verification(
    session: AsyncSession, user_id: UUID, email: str, token_hash: str, ttl_hours: int
) -> None:
    await session.execute(text("""
        INSERT INTO email_verifications (user_id, email, token_hash, expires_at)
        VALUES (:u, :e, :h, now() + make_interval(hours => :ttl))
    """), {"u": user_id, "e": email, "h": token_hash, "ttl": ttl_hours})


async def take_email_verification(session: AsyncSession, token_hash: str) -> Any:
    """Marks the link used and returns it, if it is unused and not expired."""
    return (await session.execute(text("""
        UPDATE email_verifications SET used_at = now()
        WHERE token_hash = :h AND used_at IS NULL AND expires_at > now()
        RETURNING user_id, email
    """), {"h": token_hash})).one_or_none()


async def insert_recovery_token(
    session: AsyncSession, user_id: UUID, token_hash: str, ttl_minutes: int, ip: str | None
) -> None:
    # A new link replaces older ones.
    await session.execute(text("""
        UPDATE recovery_tokens SET used_at = now() WHERE user_id = :u AND used_at IS NULL
    """), {"u": user_id})
    await session.execute(text("""
        INSERT INTO recovery_tokens (user_id, token_hash, expires_at, request_ip)
        VALUES (:u, :h, now() + make_interval(mins => :ttl), CAST(:ip AS inet))
    """), {"u": user_id, "h": token_hash, "ttl": ttl_minutes, "ip": ip})


async def recovery_token(session: AsyncSession, token_hash: str, *, for_update: bool = False) -> Any:
    lock = " FOR UPDATE OF r" if for_update else ""
    return (await session.execute(text(f"""
        SELECT r.id, r.user_id, u.full_name, u.phone, u.phone_verified_at IS NOT NULL AS phone_verified
        FROM recovery_tokens r JOIN users u ON u.id = r.user_id
        WHERE r.token_hash = :h AND r.used_at IS NULL AND r.expires_at > now(){lock}
    """), {"h": token_hash})).one_or_none()


async def recent_recovery_requests(session: AsyncSession, user_id: UUID) -> int:
    return int((await session.execute(text("""
        SELECT count(*) FROM recovery_tokens WHERE user_id = :u AND created_at > now() - interval '1 hour'
    """), {"u": user_id})).scalar_one())


async def use_recovery_token(session: AsyncSession, token_id: UUID) -> None:
    await session.execute(text("UPDATE recovery_tokens SET used_at = now() WHERE id = :id"), {"id": token_id})


# --- Membership (tenant transaction) ----------------------------------------------------


async def get_member(session: AsyncSession, user_id: UUID) -> Any:
    return (await session.execute(
        text("SELECT id, role, status FROM tenant_members WHERE user_id = :u"), {"u": user_id}
    )).one_or_none()


async def upsert_student_member(session: AsyncSession, user_id: UUID) -> Any:
    """Creates the student member, or brings back one who left. Suspended members stay suspended."""
    return (await session.execute(text("""
        INSERT INTO tenant_members (tenant_id, user_id, role)
        VALUES (current_tenant_id(), :u, 'student')
        ON CONFLICT (tenant_id, user_id) DO UPDATE
            SET status = CASE WHEN tenant_members.status = 'suspended' THEN 'suspended' ELSE 'active' END
        RETURNING id, role, status
    """), {"u": user_id})).one()


async def clear_unverified_password(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(text("UPDATE users SET password_hash = NULL WHERE id = :u"), {"u": user_id})


async def mark_own_email_verified(session: AsyncSession, user_id: UUID) -> None:
    await session.execute(text("""
        UPDATE users SET email_verified_at = COALESCE(email_verified_at, now())
        WHERE id = :u AND email IS NOT NULL
    """), {"u": user_id})


async def recent_email_verifications(session: AsyncSession, user_id: UUID) -> int:
    return int((await session.execute(text("""
        SELECT count(*) FROM email_verifications WHERE user_id = :u AND created_at > now() - interval '1 hour'
    """), {"u": user_id})).scalar_one())
