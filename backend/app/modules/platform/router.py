from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response

from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.integrations.sms import SmsSender, get_sms_sender
from app.modules.auth.dependencies import user_agent
from app.modules.auth.schemas import OtpRequest, OtpRequested
from app.modules.platform import auth, service
from app.modules.platform.auth import Admin, AdminTx, PlatformLogin, PlatformMe, PlatformRefresh, PlatformTokens
from app.modules.platform.schemas import (
    PayoutCreate,
    PayoutRow,
    PlatformPaymentPage,
    TenantCreate,
    TenantCreated,
    TenantRow,
    TenantStatus,
    TenantUpdate,
)

# EduZone staff only. No tenant host; reachable only from PLATFORM_ALLOWED_CIDRS.
router = APIRouter(prefix="/platform", tags=["platform"])


@router.post("/auth/otp/request", response_model=OtpRequested, status_code=202)
async def request_code(body: OtpRequest, request: Request,
                       sms: Annotated[SmsSender, Depends(get_sms_sender)]) -> OtpRequested:
    return await auth.request_code(body.phone, auth.check_network(request), sms)


@router.post("/auth/login", response_model=PlatformTokens)
async def login(body: PlatformLogin, request: Request) -> PlatformTokens:
    return await auth.login(body, auth.check_network(request), user_agent(request))


@router.post("/auth/refresh", response_model=PlatformTokens)
async def refresh(body: PlatformRefresh, request: Request) -> PlatformTokens:
    return await auth.refresh(body.refresh_token, auth.check_network(request), user_agent(request))


@router.post("/auth/logout", status_code=204)
async def logout(actor: Admin) -> Response:
    await auth.logout(actor)
    return Response(status_code=204)


@router.get("/auth/me", response_model=PlatformMe)
async def me(actor: Admin) -> PlatformMe:
    return await auth.me(actor)


@router.get("/tenants", response_model=list[TenantRow])
async def list_tenants(actor: Admin, session: AdminTx, status: TenantStatus | None = None) -> list[TenantRow]:
    return await service.list_tenants(session, status=status)


@router.post("/tenants", response_model=TenantCreated, status_code=201)
async def create_tenant(body: TenantCreate, actor: Admin, session: AdminTx) -> TenantCreated:
    return await service.create_tenant(session, actor, body)


@router.get("/tenants/{tenant_id}", response_model=TenantRow)
async def get_tenant(tenant_id: UUID, actor: Admin, session: AdminTx) -> TenantRow:
    return await service.get_tenant(session, tenant_id)


@router.patch("/tenants/{tenant_id}", response_model=TenantRow)
async def update_tenant(tenant_id: UUID, body: TenantUpdate, actor: Admin, session: AdminTx) -> TenantRow:
    return await service.update_tenant(session, actor, tenant_id, body)


@router.get("/tenants/{tenant_id}/payouts", response_model=list[PayoutRow])
async def list_payouts(tenant_id: UUID, actor: Admin, session: AdminTx) -> list[PayoutRow]:
    return await service.list_payouts(session, tenant_id)


@router.post("/tenants/{tenant_id}/payouts", response_model=PayoutRow, status_code=201)
async def record_payout(tenant_id: UUID, body: PayoutCreate, actor: Admin, session: AdminTx) -> PayoutRow:
    return await service.record_payout(session, actor, tenant_id, body)


@router.get("/payments", response_model=PlatformPaymentPage)
async def list_payments(
    actor: Admin, session: AdminTx,
    tenant_id: UUID | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> PlatformPaymentPage:
    return await service.list_payments(session, tenant_id=tenant_id, status=status, cursor=cursor, limit=limit)
