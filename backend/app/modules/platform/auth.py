"""Platform admin sign-in: phone code by SMS **and** an authenticator-app code, then a
short-lived access token plus a refresh token held in `platform_admin_sessions`.

Separate from tenant sign-in in every way: its own tokens (typ "platform", never accepted by
tenant routes and vice versa), its own session table, the eduzone_admin database role, and an
optional network allowlist (the VPN) checked on every request.
"""

import ipaddress
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.db import AdminSession
from app.core.errors import ApiError
from app.core.i18n import t
from app.integrations.sms import SmsSender
from app.modules.auth import repository as auth_repo
from app.modules.auth.dependencies import client_ip, user_agent
from app.modules.auth.schemas import OtpRequested, _PhoneBody
from app.modules.auth.service import check_and_consume_otp
from app.modules.auth.tokens import hash_otp, hash_refresh_token, new_otp_code, new_refresh_token
from app.modules.platform import totp

_TYP = "platform"


class PlatformLogin(_PhoneBody):
    code: str = Field(pattern=r"^\d{6}$")          # from the SMS
    totp: str = Field(pattern=r"^\d{6}$")          # from the authenticator app


class PlatformRefresh(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=200)


class PlatformTokens(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class PlatformMe(BaseModel):
    user_id: UUID
    full_name: str
    phone: str | None


def _invalid() -> ApiError:
    # One message for every failure, so it doesn't reveal which factor was wrong.
    return ApiError("INVALID_LOGIN", "The codes are wrong or have expired.", status_code=401)


def check_network(request: Request) -> str | None:
    """Platform routes are reachable only from the allowed networks (e.g. the VPN)."""
    s = get_settings()
    ip = client_ip(request)
    if not s.platform_allowed_cidrs:
        if s.environment != "local":
            raise ApiError("NOT_FOUND", "Not found.", status_code=404)
        return ip
    try:
        addr = ipaddress.ip_address(ip or "")
    except ValueError:
        raise ApiError("NOT_FOUND", "Not found.", status_code=404) from None
    if not any(addr in ipaddress.ip_network(c, strict=False) for c in s.platform_allowed_cidrs):
        raise ApiError("NOT_FOUND", "Not found.", status_code=404)
    return ip


# --- sign in --------------------------------------------------------------------------

_ADMIN_BY_PHONE = """
    SELECT u.id, u.full_name, u.preferred_language, pa.totp_secret, pa.last_totp_step
    FROM users u JOIN platform_admins pa ON pa.user_id = u.id
    WHERE u.phone = :p AND u.is_platform_admin
"""


async def request_code(phone: str, ip: str | None, sms: SmsSender) -> OtpRequested:
    """Same answer whether or not the phone belongs to an admin; a code is sent only if it does."""
    s = get_settings()
    code = new_otp_code()
    async with AdminSession() as session, session.begin():
        await auth_repo.lock_phone(session, phone)
        stats = await auth_repo.otp_request_stats(session, phone, ip, s.otp_resend_cooldown_seconds)
        if stats.in_cooldown or stats.phone_last_hour >= s.otp_max_per_phone_per_hour \
                or stats.ip_last_hour >= s.otp_max_per_ip_per_hour:
            raise ApiError("OTP_RATE_LIMITED", "Too many code requests. Please wait and try again.", 429)
        admin = (await session.execute(text(_ADMIN_BY_PHONE), {"p": phone})).one_or_none()
        if admin is not None:
            await auth_repo.insert_otp(session, phone, hash_otp(phone, code), s.otp_ttl_seconds, ip)
    if admin is not None:
        await sms.send(phone, t("sms.admin_code", admin.preferred_language, code=code,
                                minutes=s.otp_ttl_seconds // 60))
    return OtpRequested(expires_in=s.otp_ttl_seconds, resend_after=s.otp_resend_cooldown_seconds)


async def login(body: PlatformLogin, ip: str | None, ua: str | None) -> PlatformTokens:
    s = get_settings()
    try:
        # SMS code first: wrong guesses are counted and lock the code, which also limits
        # guessing the authenticator code (a new SMS is needed after any failure).
        await check_and_consume_otp(body.phone, body.code, full_name="-")
    except ApiError as exc:
        if exc.code in ("OTP_TOO_MANY_ATTEMPTS",):
            raise
        raise _invalid() from None
    async with AdminSession() as session, session.begin():
        admin = (await session.execute(text(_ADMIN_BY_PHONE + " FOR UPDATE OF pa"), {"p": body.phone})).one_or_none()
        if admin is None:
            raise _invalid()
        step = totp.verify(admin.totp_secret, body.totp, last_used_step=admin.last_totp_step)
        if step is None:
            raise _invalid()
        await session.execute(text("UPDATE platform_admins SET last_totp_step = :s WHERE user_id = :u"),
                              {"s": step, "u": admin.id})
        await session.execute(text("UPDATE users SET last_login_at = now() WHERE id = :u"), {"u": admin.id})
        refresh = new_refresh_token()
        session_id = (await session.execute(text("""
            INSERT INTO platform_admin_sessions (user_id, refresh_token_hash, ip_address, user_agent, expires_at)
            VALUES (:u, :h, CAST(:ip AS inet), :ua, now() + make_interval(hours => :hours))
            RETURNING id
        """), {"u": admin.id, "h": hash_refresh_token(refresh), "ip": ip, "ua": ua,
               "hours": s.platform_session_hours})).scalar_one()
        await write_audit(session, actor_user_id=admin.id, action="platform.login", entity_type="user",
                          entity_id=admin.id, ip=ip)
    return _tokens(admin.id, session_id, refresh)


async def refresh(token: str, ip: str | None, ua: str | None) -> PlatformTokens:
    """Rotates the refresh token. The session keeps its original expiry (no sliding)."""
    async with AdminSession() as session, session.begin():
        row = (await session.execute(text("""
            SELECT s.id, s.user_id FROM platform_admin_sessions s
            JOIN users u ON u.id = s.user_id AND u.is_platform_admin
            WHERE s.refresh_token_hash = :h AND s.revoked_at IS NULL AND s.expires_at > now()
            FOR UPDATE OF s
        """), {"h": hash_refresh_token(token)})).one_or_none()
        if row is None:
            raise ApiError("SESSION_INVALID", "Please sign in again.", status_code=401)
        new = new_refresh_token()
        await session.execute(text("""
            UPDATE platform_admin_sessions SET refresh_token_hash = :h, last_seen_at = now(),
                   ip_address = CAST(:ip AS inet), user_agent = :ua
            WHERE id = :id
        """), {"h": hash_refresh_token(new), "ip": ip, "ua": ua, "id": row.id})
    return _tokens(row.user_id, row.id, new)


def _tokens(user_id: UUID, session_id: UUID, refresh_token: str) -> PlatformTokens:
    s = get_settings()
    now = int(time.time())
    access = jwt.encode({"typ": _TYP, "sub": str(user_id), "sid": str(session_id), "iat": now,
                         "exp": now + s.platform_access_ttl_seconds}, s.jwt_secret, algorithm="HS256")
    return PlatformTokens(access_token=access, refresh_token=refresh_token, expires_in=s.platform_access_ttl_seconds)


# --- dependencies for platform routes --------------------------------------------------

@dataclass(frozen=True, slots=True)
class PlatformActor:
    user_id: UUID
    session_id: UUID
    ip: str | None


_bearer = HTTPBearer(auto_error=False, description="Platform admin access token")


async def current_admin(
    request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> PlatformActor:
    ip = check_network(request)
    if credentials is None:
        raise ApiError("UNAUTHORIZED", "Please sign in.", status_code=401)
    try:
        claims = jwt.decode(credentials.credentials, get_settings().jwt_secret, algorithms=["HS256"],
                            options={"require": ["exp", "sub", "sid", "typ"]})
        if claims["typ"] != _TYP:
            raise jwt.InvalidTokenError("not a platform token")
        user_id, session_id = UUID(claims["sub"]), UUID(claims["sid"])
    except (jwt.PyJWTError, ValueError):
        raise ApiError("UNAUTHORIZED", "Please sign in.", status_code=401) from None
    async with AdminSession() as session:
        ok = (await session.execute(text("""
            SELECT 1 FROM platform_admin_sessions s
            JOIN users u ON u.id = s.user_id AND u.is_platform_admin
            JOIN platform_admins pa ON pa.user_id = u.id
            WHERE s.id = :sid AND s.user_id = :uid AND s.revoked_at IS NULL AND s.expires_at > now()
        """), {"sid": session_id, "uid": user_id})).first()
    if not ok:
        raise ApiError("SESSION_REVOKED", "Please sign in again.", status_code=401)
    return PlatformActor(user_id, session_id, ip)


Admin = Annotated[PlatformActor, Depends(current_admin)]


async def admin_tx() -> AsyncIterator[AsyncSession]:
    """One eduzone_admin (BYPASSRLS) transaction per platform request. Never for tenant routes."""
    async with AdminSession() as session, session.begin():
        yield session


AdminTx = Annotated[AsyncSession, Depends(admin_tx, scope="function")]


async def logout(actor: PlatformActor) -> None:
    async with AdminSession() as session, session.begin():
        await session.execute(text("""
            UPDATE platform_admin_sessions SET revoked_at = now(), revoke_reason = 'logout'
            WHERE id = :id AND revoked_at IS NULL
        """), {"id": actor.session_id})


async def me(actor: PlatformActor) -> PlatformMe:
    async with AdminSession() as session:
        r = (await session.execute(text("SELECT id, full_name, phone FROM users WHERE id = :u"),
                                   {"u": actor.user_id})).one()
    return PlatformMe(user_id=r.id, full_name=r.full_name, phone=r.phone)
