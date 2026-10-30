"""Accounts, sign-in, devices, phone and email checks, recovery (CLAUDE.md sections 10-11).

One account per person across all tenants. Signing in needs the password (or Google) and, on a
device that hasn't passed an SMS check, a code sent to the verified phone. Signing in signs the
account out everywhere else (one active device), except for staff of any organization.
"""

import asyncio
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.i18n import t
from app.integrations.email import EmailSender
from app.integrations.sms import SmsSender
from app.modules.auth import otp
from app.modules.auth import repository as repo
from app.core.tenancy import TenantContext, tenant_transaction, user_transaction
from app.modules.auth.dependencies import SIGNED_IN_ELSEWHERE, AuthContext, UserContext, current_member, session_ended
from app.modules.auth.google import GoogleVerifier
from app.modules.auth.passwords import hash_password, needs_rehash, verify_password
from app.modules.auth.schemas import (
    DeviceCheck,
    DeviceVerify,
    GoogleLogin,
    Login,
    LoginResult,
    Me,
    OtpRequested,
    PhoneVerify,
    Workspace,
    ProfileUpdate,
    RecoveryComplete,
    RecoveryStarted,
    Register,
    TokenPair,
)
from app.modules.auth.tokens import (
    AccessClaims,
    decode_device_challenge,
    hash_link_token,
    hash_refresh_token,
    issue_access_token,
    issue_device_challenge,
    new_link_token,
    new_refresh_token,
)


def _invalid_login() -> ApiError:
    # One message for unknown email and wrong password, so it doesn't reveal who has an account.
    return ApiError("LOGIN_INVALID", "The email or password is wrong.", 400)


def _link_invalid() -> ApiError:
    return ApiError("LINK_INVALID", "This link has expired or was already used. Request a new one.", 400)


def phone_hint(phone: str) -> str:
    return f"•••• {phone[-4:]}"


def _token_pair(user_id: UUID, session_id: UUID, refresh: str) -> TokenPair:
    return TokenPair(
        access_token=issue_access_token(AccessClaims(user_id, session_id)),
        refresh_token=refresh,
        expires_in=get_settings().access_token_ttl_seconds,
    )


async def _start_session(
    session: AsyncSession, user_id: UUID, device_id: str, ip: str | None, ua: str | None
) -> TokenPair:
    # One active device per account; staff of any organization may use several.
    if not await repo.is_staff_anywhere(session, user_id):
        await repo.revoke_user_sessions(session, user_id, SIGNED_IN_ELSEWHERE)
    refresh = new_refresh_token()
    session_id = await repo.insert_session(
        session, user_id, device_id, hash_refresh_token(refresh), get_settings().refresh_token_ttl_days, ip, ua
    )
    await repo.touch_login(session, user_id)
    return _token_pair(user_id, session_id, refresh)


class _PendingSms:
    """An SMS to send once the transaction has committed."""

    def __init__(self, phone: str, text: str) -> None:
        self.phone, self.text = phone, text


async def _sign_in_or_check_device(
    session: AsyncSession, user: Any, device_id: str, ip: str | None, ua: str | None
) -> tuple[LoginResult, _PendingSms | None]:
    known = await repo.is_trusted_device(session, user.id, device_id)
    if known or not user.phone_verified:
        # No verified phone yet (new account): nothing to check against; this device is theirs.
        if not known:
            await repo.trust_device(session, user.id, device_id, ua)
        tokens = await _start_session(session, user.id, device_id, ip, ua)
        return LoginResult(status="signed_in", tokens=tokens), None
    s = get_settings()
    code = await otp.issue(session, user.phone, "new_device", ip)
    sms = _PendingSms(user.phone, t("sms.new_device", user.preferred_language, code=code,
                                    minutes=s.otp_ttl_seconds // 60))
    check = DeviceCheck(
        challenge=issue_device_challenge(user.id, device_id), phone_hint=phone_hint(user.phone),
        expires_in=s.otp_ttl_seconds, resend_after=s.otp_resend_cooldown_seconds,
    )
    return LoginResult(status="device_check", device_check=check), sms


async def _send(sms: SmsSender, pending: _PendingSms | None) -> None:
    if pending is not None:
        await sms.send(pending.phone, pending.text)


# --- Register and sign in ---------------------------------------------------------------


async def register(body: Register, ip: str | None, ua: str | None, emails: EmailSender, site_url: str) -> TokenPair:
    s = get_settings()
    if len(body.password) < s.password_min_length:
        raise ApiError("PASSWORD_TOO_SHORT", f"Use at least {s.password_min_length} characters.", 422)
    link = new_link_token()
    async with AppSession() as session, session.begin():
        await repo.lock_email(session, body.email)
        if await repo.get_user_by_email(session, body.email) is not None:
            raise ApiError("EMAIL_TAKEN", "An account with this email already exists. Sign in instead.", 409)
        user_id = await repo.create_user(session, email=body.email, password_hash=hash_password(body.password),
                                         full_name=body.full_name, email_verified=False)
        await repo.trust_device(session, user_id, body.device_id, ua)
        tokens = await _start_session(session, user_id, body.device_id, ip, ua)
        await repo.insert_email_verification(session, user_id, body.email, hash_link_token(link),
                                             s.email_verification_ttl_hours)
    await _send_verification_email(emails, body.email, body.full_name, link, site_url)
    return tokens


async def login(body: Login, ip: str | None, ua: str | None, sms: SmsSender) -> LoginResult:
    s = get_settings()
    failure: ApiError | None = None
    async with AppSession() as session, session.begin():
        await repo.lock_email(session, body.email)
        recent = await repo.recent_failures(session, body.email, ip, s.login_window_minutes)
        if recent.by_email >= s.login_max_failures_per_email or recent.by_ip >= s.login_max_failures_per_ip:
            raise ApiError("LOGIN_RATE_LIMITED", "Too many attempts. Wait a few minutes or reset your password.", 429)
        user = await repo.get_user_by_email(session, body.email)
        ok = verify_password(user.password_hash if user else None, body.password)
        await repo.record_attempt(session, body.email, ip, ok)
        if not ok:
            failure = _invalid_login()  # raised after commit, so the failed attempt is counted
        else:
            if needs_rehash(user.password_hash):
                await repo.set_password(session, user.id, hash_password(body.password))
            result, pending = await _sign_in_or_check_device(session, user, body.device_id, ip, ua)
    if failure:
        raise failure
    await _send(sms, pending)
    return result


async def google_login(
    body: GoogleLogin, verifier: GoogleVerifier, ip: str | None, ua: str | None, sms: SmsSender
) -> LoginResult:
    identity = await asyncio.to_thread(verifier.verify, body.id_token)  # fetches Google's keys
    async with AppSession() as session, session.begin():
        user_id = await repo.user_for_identity(session, "google", identity.subject)
        if user_id is None:
            if not identity.email or not identity.email_verified:
                raise ApiError("GOOGLE_EMAIL_UNVERIFIED", "Your Google account has no verified email.", 400)
            email = identity.email.strip().lower()
            await repo.lock_email(session, email)
            existing = await repo.get_user_by_email(session, email, for_update=True)
            if existing is None:
                user_id = await repo.create_user(session, email=email, password_hash=None,
                                                 full_name=(identity.name or email.split("@")[0])[:120],
                                                 email_verified=True)
            else:
                user_id = existing.id
                if not existing.email_verified:
                    # Someone registered this address without proving it. Google proves the real
                    # owner: drop that password and its sessions so they can't stay in.
                    await repo.clear_unverified_password(session, user_id)
                    await repo.revoke_user_sessions(session, user_id, "email_claimed")
                await repo.mark_email_verified(session, user_id, email)
            await repo.link_identity(session, user_id, "google", identity.subject, email)
        user = await repo.get_user(session, user_id)
        result, pending = await _sign_in_or_check_device(session, user, body.device_id, ip, ua)
    await _send(sms, pending)
    return result


async def verify_device(body: DeviceVerify, ip: str | None, ua: str | None) -> TokenPair:
    challenge = decode_device_challenge(body.challenge)
    if challenge.device_id != body.device_id:
        raise ApiError("CHALLENGE_EXPIRED", "This sign-in has expired. Please sign in again.", 401)
    async with AppSession() as session:
        user = await repo.get_user(session, challenge.user_id)
    if not user.phone_verified:
        raise ApiError("CHALLENGE_EXPIRED", "This sign-in has expired. Please sign in again.", 401)
    await otp.consume(user.phone, "new_device", body.code)
    async with AppSession() as session, session.begin():
        await repo.trust_device(session, user.id, body.device_id, ua)
        return await _start_session(session, user.id, body.device_id, ip, ua)


async def resend_device_code(challenge_token: str, ip: str | None, sms: SmsSender) -> OtpRequested:
    challenge = decode_device_challenge(challenge_token)
    s = get_settings()
    async with AppSession() as session, session.begin():
        user = await repo.get_user(session, challenge.user_id)
        if not user.phone_verified:
            raise ApiError("CHALLENGE_EXPIRED", "This sign-in has expired. Please sign in again.", 401)
        code = await otp.issue(session, user.phone, "new_device", ip)
    await sms.send(user.phone, t("sms.new_device", user.preferred_language, code=code, minutes=s.otp_ttl_seconds // 60))
    return OtpRequested(expires_in=s.otp_ttl_seconds, resend_after=s.otp_resend_cooldown_seconds)


async def refresh_session(refresh_token: str, ip: str | None, ua: str | None) -> TokenPair:
    s = get_settings()
    async with AppSession() as session, session.begin():
        row = await repo.session_by_refresh_hash_for_update(session, hash_refresh_token(refresh_token))
        if row is None or row.expired:
            raise ApiError("SESSION_INVALID", "Please sign in again.", 401)
        if row.revoked:
            raise session_ended(row.revoke_reason)
        refresh = new_refresh_token()
        await repo.rotate_session(session, row.id, hash_refresh_token(refresh), s.refresh_token_ttl_days, ip, ua)
    return _token_pair(row.user_id, row.id, refresh)


async def logout(session_id: UUID) -> None:
    async with AppSession() as session, session.begin():
        await repo.revoke_session(session, session_id, "logout")


# --- Profile ----------------------------------------------------------------------------


async def member_context(user: UserContext, tenant: TenantContext | None) -> AuthContext:
    """Membership in the tenant of the request; none on the main host."""
    if tenant is None:
        return AuthContext(user.user_id, None, None, user.session_id)
    async with tenant_transaction(tenant.id) as session:
        return await current_member(user, session)


async def workspaces(user_id: UUID) -> list[Workspace]:
    async with user_transaction(user_id) as session:
        return [Workspace(slug=r.slug, name=r.name, role=r.role, status=r.status) for r in await repo.workspaces(session)]


async def get_me(auth: AuthContext) -> Me:
    async with AppSession() as session:
        u = await repo.get_user(session, auth.user_id)
    return Me(
        user_id=u.id, full_name=u.full_name, email=u.email, email_verified=u.email_verified,
        phone=u.phone, phone_verified=u.phone_verified, has_password=u.password_hash is not None,
        preferred_language=u.preferred_language, exam=u.exam, exam_year=u.exam_year, school=u.school,
        member_id=auth.member_id, role=auth.role, workspaces=await workspaces(auth.user_id),
    )


async def update_profile(user_id: UUID, body: ProfileUpdate) -> None:
    values = body.model_dump(exclude_unset=True)
    for required in ("full_name", "preferred_language"):
        if required in values and values[required] is None:
            raise ApiError("VALIDATION_ERROR", f"{required} can't be empty.", 422)
    if "full_name" in values:
        values["full_name"] = " ".join(values["full_name"].split())
    if values.get("school") is not None:
        values["school"] = values["school"].strip() or None
    async with AppSession() as session, session.begin():
        await repo.update_profile(session, user_id, values)


# --- Phone ------------------------------------------------------------------------------


def _phone_taken() -> ApiError:
    return ApiError("PHONE_IN_USE", "This number is linked to another account.", 409)


async def request_phone_code(user_id: UUID, phone: str, ip: str | None, sms: SmsSender) -> OtpRequested:
    s = get_settings()
    async with AppSession() as session, session.begin():
        owner = await repo.phone_owner(session, phone)
        if owner is not None and owner != user_id:
            raise _phone_taken()
        code = await otp.issue(session, phone, "verify_phone", ip)
        lang = (await repo.get_user(session, user_id)).preferred_language
    await sms.send(phone, t("sms.verify_phone", lang, code=code, minutes=s.otp_ttl_seconds // 60))
    return OtpRequested(expires_in=s.otp_ttl_seconds, resend_after=s.otp_resend_cooldown_seconds)


async def verify_phone(user_id: UUID, body: PhoneVerify, ua: str | None) -> None:
    await otp.consume(body.phone, "verify_phone", body.code)
    async with AppSession() as session, session.begin():
        await otp.lock(session, body.phone)
        owner = await repo.phone_owner(session, body.phone)
        if owner is not None and owner != user_id:
            raise _phone_taken()
        await repo.set_verified_phone(session, user_id, body.phone)
        # The phone was proven on this device, so it counts as a known device.
        await repo.trust_device(session, user_id, body.device_id, ua)


# --- Email ------------------------------------------------------------------------------


async def _send_verification_email(emails: EmailSender, email: str, name: str, token: str, site_url: str) -> None:
    hours = get_settings().email_verification_ttl_hours
    await emails.send(email, t("email.verify.subject"),
                      t("email.verify.body", name=name, link=f"{site_url}/verify-email?token={token}", hours=hours))


async def resend_email_verification(user_id: UUID, emails: EmailSender, site_url: str) -> None:
    s = get_settings()
    link = new_link_token()
    async with AppSession() as session, session.begin():
        u = await repo.get_user(session, user_id)
        if u.email is None or u.email_verified:
            return
        if await repo.recent_email_verifications(session, user_id) >= 5:
            raise ApiError("EMAIL_RATE_LIMITED", "We've sent several emails already. Check your inbox and spam folder.", 429)
        await repo.insert_email_verification(session, user_id, u.email, hash_link_token(link),
                                             s.email_verification_ttl_hours)
    await _send_verification_email(emails, u.email, u.full_name, link, site_url)


async def verify_email(token: str) -> None:
    async with AppSession() as session, session.begin():
        row = await repo.take_email_verification(session, hash_link_token(token))
        if row is None or not await repo.mark_email_verified(session, row.user_id, row.email):
            raise _link_invalid()


# --- Recovery: email link, then (if the account has a verified phone) an SMS code --------


async def request_recovery(email: str, ip: str | None, emails: EmailSender, site_url: str) -> None:
    """Same answer whether or not the email has an account."""
    s = get_settings()
    link = new_link_token()
    async with AppSession() as session, session.begin():
        await repo.lock_email(session, email)
        user = await repo.get_user_by_email(session, email)
        if user is None or await repo.recent_recovery_requests(session, user.id) >= 5:
            return
        await repo.insert_recovery_token(session, user.id, hash_link_token(link), s.recovery_ttl_minutes, ip)
    await emails.send(email, t("email.recovery.subject", user.preferred_language),
                      t("email.recovery.body", user.preferred_language, name=user.full_name,
                        link=f"{site_url}/recover/{link}", minutes=s.recovery_ttl_minutes))


async def start_recovery(token: str, ip: str | None, sms: SmsSender) -> RecoveryStarted:
    s = get_settings()
    async with AppSession() as session, session.begin():
        row = await repo.recovery_token(session, hash_link_token(token))
        if row is None:
            raise _link_invalid()
        if not row.phone_verified:
            return RecoveryStarted(needs_code=False)
        try:
            code = await otp.issue(session, row.phone, "reset_password", ip)
        except ApiError as exc:
            if exc.code != "OTP_RATE_LIMITED":
                raise
            code = None  # a code went out moments ago (page reloaded); that one still works
    if code is not None:
        await sms.send(row.phone, t("sms.recovery", code=code, minutes=s.otp_ttl_seconds // 60))
    return RecoveryStarted(needs_code=True, phone_hint=phone_hint(row.phone), resend_after=s.otp_resend_cooldown_seconds)


async def complete_recovery(body: RecoveryComplete, ip: str | None, ua: str | None) -> TokenPair:
    s = get_settings()
    if len(body.password) < s.password_min_length:
        raise ApiError("PASSWORD_TOO_SHORT", f"Use at least {s.password_min_length} characters.", 422)
    token_hash = hash_link_token(body.token)
    async with AppSession() as session:
        row = await repo.recovery_token(session, token_hash)
    if row is None:
        raise _link_invalid()
    if row.phone_verified:
        if body.code is None:
            raise ApiError("OTP_REQUIRED", "Enter the code we sent to your phone.", 400)
        await otp.consume(row.phone, "reset_password", body.code)
    async with AppSession() as session, session.begin():
        row = await repo.recovery_token(session, token_hash, for_update=True)
        if row is None:
            raise _link_invalid()
        await repo.use_recovery_token(session, row.id)
        await repo.set_password(session, row.user_id, hash_password(body.password))
        await repo.mark_own_email_verified(session, row.user_id)  # they opened the emailed link
        await repo.revoke_user_sessions(session, row.user_id, "password_reset")
        await repo.trust_device(session, row.user_id, body.device_id, ua)
        return await _start_session(session, row.user_id, body.device_id, ip, ua)
