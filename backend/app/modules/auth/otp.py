"""SMS codes for every purpose (phone check, new device, recovery, admin sign-in).

Limits per destination and purpose: a resend cooldown and an hourly cap; plus an hourly cap
per IP across all purposes. A code is spent on success; wrong guesses are counted in their own
transaction and lock the code after `otp_max_attempts`.
"""

from typing import Literal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError
from app.modules.auth.tokens import hash_otp, new_otp_code, otp_matches

Purpose = Literal["login", "verify_phone", "new_device", "reset_password"]


def rate_limited() -> ApiError:
    return ApiError("OTP_RATE_LIMITED", "Too many code requests. Please wait and try again.", 429)


def invalid_code() -> ApiError:
    return ApiError("OTP_INVALID", "The code is wrong or has expired.", 400)


async def lock(session: AsyncSession, destination: str) -> None:
    """Serialise code work per destination for the rest of the transaction."""
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtext('otp:' || :d))"), {"d": destination})


async def issue(session: AsyncSession, destination: str, purpose: Purpose, ip: str | None) -> str:
    """Checks the limits and stores a new code (hashed). Returns the code to send."""
    s = get_settings()
    await lock(session, destination)
    stats = (await session.execute(text("""
        SELECT
          EXISTS (SELECT 1 FROM otp_codes
                  WHERE destination = :d AND purpose = :p
                    AND created_at > now() - make_interval(secs => CAST(:cooldown AS integer))) AS in_cooldown,
          (SELECT count(*) FROM otp_codes
           WHERE destination = :d AND purpose = :p AND created_at > now() - interval '1 hour') AS dest_last_hour,
          (SELECT count(*) FROM otp_codes
           WHERE CAST(:ip AS inet) IS NOT NULL AND request_ip = CAST(:ip AS inet)
             AND created_at > now() - interval '1 hour')                                    AS ip_last_hour
    """), {"d": destination, "p": purpose, "ip": ip, "cooldown": s.otp_resend_cooldown_seconds})).one()
    if (
        stats.in_cooldown
        or stats.dest_last_hour >= s.otp_max_per_phone_per_hour
        or stats.ip_last_hour >= s.otp_max_per_ip_per_hour
    ):
        raise rate_limited()
    code = new_otp_code()
    await session.execute(text("""
        INSERT INTO otp_codes (destination, purpose, code_hash, expires_at, request_ip)
        VALUES (:d, :p, :h, now() + make_interval(secs => CAST(:ttl AS integer)), CAST(:ip AS inet))
    """), {"d": destination, "p": purpose, "h": hash_otp(destination, code, purpose),
           "ttl": s.otp_ttl_seconds, "ip": ip})
    return code


async def consume(
    destination: str, purpose: Purpose, code: str, *, sessions: async_sessionmaker[AsyncSession] = AppSession
) -> None:
    """Checks and spends the latest code. Runs in its own transaction so a wrong guess is
    counted even though the request fails."""
    s = get_settings()
    failure: ApiError | None = None
    async with sessions() as session, session.begin():
        await lock(session, destination)
        otp = (await session.execute(text("""
            SELECT id, code_hash, attempts, consumed_at IS NOT NULL AS consumed, expires_at <= now() AS expired
            FROM otp_codes WHERE destination = :d AND purpose = :p
            ORDER BY created_at DESC LIMIT 1
            FOR UPDATE
        """), {"d": destination, "p": purpose})).one_or_none()
        if otp is None or otp.consumed or otp.expired:
            raise invalid_code()
        if otp.attempts >= s.otp_max_attempts:
            raise ApiError("OTP_TOO_MANY_ATTEMPTS", "Too many wrong codes. Request a new code.", 429)
        if otp_matches(otp.code_hash, destination, code, purpose):
            await session.execute(text("UPDATE otp_codes SET consumed_at = now() WHERE id = :id"), {"id": otp.id})
        else:
            await session.execute(text("UPDATE otp_codes SET attempts = attempts + 1 WHERE id = :id"), {"id": otp.id})
            failure = invalid_code()
    if failure:
        raise failure
