from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from app.core.tenancy import CurrentTenant, TenantSession
from app.integrations.sms import SmsSender, get_sms_sender
from app.modules.auth import service
from app.modules.auth.dependencies import CurrentMember, client_ip, user_agent
from app.modules.auth.schemas import Me, OtpRequest, OtpRequested, OtpVerify, RefreshRequest, TokenPair

# Shared by students and staff, always on a tenant host.
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/otp/request", response_model=OtpRequested, status_code=202)
async def request_otp(
    body: OtpRequest, request: Request, tenant: CurrentTenant,
    sms: Annotated[SmsSender, Depends(get_sms_sender)],
) -> OtpRequested:
    return await service.request_otp(tenant, body.phone, client_ip(request), sms)


@router.post("/otp/verify", response_model=TokenPair)
async def verify_otp(body: OtpVerify, request: Request, tenant: CurrentTenant) -> TokenPair:
    return await service.login_with_otp(
        tenant, body, client_ip(request), user_agent(request)
    )


@router.post("/refresh", response_model=TokenPair)
async def refresh(body: RefreshRequest, request: Request, tenant: CurrentTenant) -> TokenPair:
    return await service.refresh_session(
        tenant, body.refresh_token, client_ip(request), user_agent(request)
    )


@router.post("/logout", status_code=204)
async def logout(auth: CurrentMember, session: TenantSession) -> Response:
    await service.logout(session, auth.session_id)
    return Response(status_code=204)


@router.get("/me", response_model=Me)
async def me(auth: CurrentMember, session: TenantSession) -> Me:
    return await service.get_me(session, auth.user_id)
