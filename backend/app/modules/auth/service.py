"""Phone OTP login, sessions and the one-device rule (CLAUDE.md sections 10-11)."""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.i18n import t
from app.core.tenancy import TenantContext, tenant_transaction
from app.integrations.sms import SmsSender
from app.modules.auth import repository as repo
from app.modules.auth.schemas import Me, OtpRequested, OtpVerify, TokenPair
from app.modules.auth.tokens import (
    AccessClaims,
    hash_otp,
    hash_refresh_token,
    issue_access_token,
    new_otp_code,
    new_refresh_token,
    otp_matches,
)
from app.modules.tenants import repository as tenants_repo

def _rate_limited() -> ApiError:
    return ApiError("OTP_RATE_LIMITED", "Too many code requests. Please wait and try again.", 429)


def _invalid_code() -> ApiError:
    return ApiError("OTP_INVALID", "The code is wrong or has expired.", 400)


def _session_invalid() -> ApiError:
    return ApiError("SESSION_INVALID", "Please sign in again.", 401)


async def request_otp(tenant: TenantContext, phone: str, ip: str | None, sms: SmsSender) -> OtpRequested:
    s = get_settings()
    code = new_otp_code()
    async with AppSession() as session, session.begin():
        await repo.lock_phone(session, phone)
        stats = await repo.otp_request_stats(session, phone, ip, s.otp_resend_cooldown_seconds)
        if (
            stats.in_cooldown
            or stats.phone_last_hour >= s.otp_max_per_phone_per_hour
            or stats.ip_last_hour >= s.otp_max_per_ip_per_hour
        ):
            raise _rate_limited()
        await repo.insert_otp(session, phone, hash_otp(phone, code), s.otp_ttl_seconds, ip)
        user = await repo.get_user_by_phone(session, phone)

    async with tenant_transaction(tenant.id) as session:
        org_name = (await tenants_repo.get_current_tenant_row(session)).name

    lang = user.preferred_language if user else "en"
    await sms.send(phone, t("sms.login_code", lang, code=code, org=org_name, minutes=s.otp_ttl_seconds // 60))
    return OtpRequested(expires_in=s.otp_ttl_seconds, resend_after=s.otp_resend_cooldown_seconds)


async def _check_and_consume_otp(phone: str, code: str, full_name: str | None) -> None:
    """Runs in its own transaction so a wrong guess is counted even though the request fails."""
    s = get_settings()
    failure: ApiError | None = None
    async with AppSession() as session, session.begin():
        await repo.lock_phone(session, phone)
        otp = await repo.latest_otp_for_update(session, phone)
        if otp is None or otp.consumed or otp.expired:
            raise _invalid_code()
        if otp.attempts >= s.otp_max_attempts:
            raise ApiError("OTP_TOO_MANY_ATTEMPTS", "Too many wrong codes. Request a new code.", 429)
        if not otp_matches(otp.code_hash, phone, code):
            await repo.increment_otp_attempts(session, otp.id)
            failure = _invalid_code()
        elif full_name is None and await repo.get_user_by_phone(session, phone) is None:
            # New number: ask for a name without spending the code.
            raise ApiError("NAME_REQUIRED", "Enter your name to create an account.", 400)
        else:
            await repo.consume_otp(session, otp.id)
    if failure:
        raise failure


async def login_with_otp(
    tenant: TenantContext, body: OtpVerify, ip: str | None, user_agent: str | None
) -> TokenPair:
    await _check_and_consume_otp(body.phone, body.code, body.full_name)

    s = get_settings()
    async with tenant_transaction(tenant.id) as session:
        user_id = await repo.upsert_user_on_login(session, body.phone, body.full_name)
        member = await repo.get_member(session, user_id)
        if member is None:
            member_id, role = await repo.insert_student_member(session, user_id), "student"
        elif member.status == "suspended":
            raise ApiError("ACCOUNT_SUSPENDED", "Your account has been suspended. Contact your teacher.", 403)
        else:
            member_id, role = member.id, member.role
            if member.status != "active":
                await repo.activate_member(session, member_id)

        # One active device per student (staff may use several).
        if role == "student":
            await repo.revoke_user_sessions(session, user_id, "signed_in_on_another_device")

        refresh = new_refresh_token()
        session_id = await repo.insert_session(
            session, user_id, body.device_id, hash_refresh_token(refresh), s.refresh_token_ttl_days,
            ip, user_agent,
        )

    return _token_pair(AccessClaims(user_id, tenant.id, member_id, role, session_id), refresh)


async def refresh_session(
    tenant: TenantContext, refresh_token: str, ip: str | None, user_agent: str | None
) -> TokenPair:
    s = get_settings()
    async with tenant_transaction(tenant.id) as session:
        # RLS: a refresh token from another tenant simply isn't found.
        row = await repo.session_by_refresh_hash_for_update(session, hash_refresh_token(refresh_token))
        if row is None or row.revoked or row.expired or row.member_status != "active":
            raise _session_invalid()
        refresh = new_refresh_token()
        await repo.rotate_session(
            session, row.id, hash_refresh_token(refresh), s.refresh_token_ttl_days, ip, user_agent
        )
    return _token_pair(AccessClaims(row.user_id, tenant.id, row.member_id, row.role, row.id), refresh)


async def logout(session: AsyncSession, session_id: UUID) -> None:
    await repo.revoke_session(session, session_id, "logout")


async def get_me(session: AsyncSession, user_id: UUID) -> Me:
    row = await repo.get_me(session, user_id)
    return Me(
        user_id=row.user_id, member_id=row.member_id, full_name=row.full_name, phone=row.phone,
        role=row.role, preferred_language=row.preferred_language,
    )


def _token_pair(claims: AccessClaims, refresh: str) -> TokenPair:
    return TokenPair(
        access_token=issue_access_token(claims),
        refresh_token=refresh,
        expires_in=get_settings().access_token_ttl_seconds,
    )
