from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def get_current_tenant_row(session: AsyncSession) -> Any:
    # RLS (tenant_self_read) already limits this to the current tenant; the filter
    # keeps the intent explicit.
    result = await session.execute(text(
        "SELECT name, slug, logo_url, primary_color FROM tenants WHERE id = current_tenant_id()"
    ))
    return result.one()
