from fastapi import APIRouter

from app.core.tenancy import TenantSession
from app.modules.tenants import service
from app.modules.tenants.schemas import TenantBranding

public_router = APIRouter(prefix="/public", tags=["public"])


@public_router.get("/tenant", response_model=TenantBranding)
async def get_tenant_branding(session: TenantSession) -> TenantBranding:
    return await service.get_branding(session)
