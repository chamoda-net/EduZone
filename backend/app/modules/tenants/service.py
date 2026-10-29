from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.tenants import repository
from app.modules.tenants.schemas import TenantBranding


async def get_branding(session: AsyncSession) -> TenantBranding:
    row = await repository.get_current_tenant_row(session)
    return TenantBranding(
        name=row.name, slug=row.slug, logo_url=row.logo_url, primary_color=row.primary_color
    )
