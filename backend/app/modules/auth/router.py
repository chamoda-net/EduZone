from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.config import get_settings
from app.core.tenancy import CurrentTenant, request_host
from app.integrations.email import EmailSender, get_email_sender
from app.integrations.sms import SmsSender, get_sms_sender
from app.modules.auth import service
from app.modules.auth.dependencies import CurrentMember, CurrentUser, client_ip, user_agent
from app.modules.auth.google import GoogleVerifier, get_google_verifier
from app.modules.auth.schemas import (
    DeviceResend,
    DeviceVerify,
    EmailVerify,
    GoogleLogin,
    Login,
    LoginResult,
    Me,
    OtpRequest,
    OtpRequested,
    PhoneVerify,
    ProfileUpdate,
    RecoveryComplete,
    RecoveryRequest,
    RecoveryStart,
    RecoveryStarted,
    RefreshRequest,
    Register,
    TokenPair,
)

# One account across all tenants. Routes that email a link take the tenant host (CurrentTenant)
# so links only ever point at a site we serve, never at a forged Host header.
router = APIRouter(prefix="/auth", tags=["auth"])

Sms = Annotated[SmsSender, Depends(get_sms_sender)]
Emails = Annotated[EmailSender, Depends(get_email_sender)]


def _site_url(request: Request) -> str:
    return f"{get_settings().site_scheme}://{request_host(request)}"


@router.post("/register", response_model=TokenPair, status_code=201)
async def register(body: Register, request: Request, tenant: CurrentTenant, emails: Emails) -> TokenPair:
    return await service.register(body, client_ip(request), user_agent(request), emails, _site_url(request))


@router.post("/login", response_model=LoginResult)
async def login(body: Login, request: Request, sms: Sms) -> LoginResult:
    return await service.login(body, client_ip(request), user_agent(request), sms)


@router.post("/google", response_model=LoginResult)
async def google(
    body: GoogleLogin, request: Request, sms: Sms, verifier: Annotated[GoogleVerifier, Depends(get_google_verifier)],
) -> LoginResult:
    return await service.google_login(body, verifier, client_ip(request), user_agent(request), sms)


@router.post("/device/verify", response_model=TokenPair)
async def verify_device(body: DeviceVerify, request: Request) -> TokenPair:
    return await service.verify_device(body, client_ip(request), user_agent(request))


@router.post("/device/resend", response_model=OtpRequested, status_code=202)
async def resend_device_code(body: DeviceResend, request: Request, sms: Sms) -> OtpRequested:
    return await service.resend_device_code(body.challenge, client_ip(request), sms)


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, request: Request) -> TokenPair:
    return await service.refresh_session(body.refresh_token, client_ip(request), user_agent(request))


@router.post("/logout", status_code=204)
async def logout(user: CurrentUser) -> Response:
    await service.logout(user.session_id)
    return Response(status_code=204)


@router.get("/me", response_model=Me)
async def me(auth: CurrentMember) -> Me:
    return await service.get_me(auth)


@router.patch("/me", response_model=Me)
async def update_me(body: ProfileUpdate, auth: CurrentMember) -> Me:
    await service.update_profile(auth.user_id, body)
    return await service.get_me(auth)


@router.post("/phone/request", response_model=OtpRequested, status_code=202)
async def request_phone_code(body: OtpRequest, request: Request, user: CurrentUser, sms: Sms) -> OtpRequested:
    return await service.request_phone_code(user.user_id, body.phone, client_ip(request), sms)


@router.post("/phone/verify", status_code=204)
async def verify_phone(body: PhoneVerify, request: Request, user: CurrentUser) -> Response:
    await service.verify_phone(user.user_id, body, user_agent(request))
    return Response(status_code=204)


@router.post("/email/resend", status_code=204)
async def resend_email(request: Request, user: CurrentUser, tenant: CurrentTenant, emails: Emails) -> Response:
    await service.resend_email_verification(user.user_id, emails, _site_url(request))
    return Response(status_code=204)


@router.post("/email/verify", status_code=204)
async def verify_email(body: EmailVerify) -> Response:
    await service.verify_email(body.token)
    return Response(status_code=204)


@router.post("/recovery/request", status_code=202)
async def request_recovery(body: RecoveryRequest, request: Request, tenant: CurrentTenant, emails: Emails) -> Response:
    await service.request_recovery(body.email, client_ip(request), emails, _site_url(request))
    return Response(status_code=202)


@router.post("/recovery/start", response_model=RecoveryStarted)
async def start_recovery(body: RecoveryStart, request: Request, sms: Sms) -> RecoveryStarted:
    return await service.start_recovery(body.token, client_ip(request), sms)


@router.post("/recovery/complete", response_model=TokenPair)
async def complete_recovery(body: RecoveryComplete, request: Request) -> TokenPair:
    return await service.complete_recovery(body, client_ip(request), user_agent(request))
