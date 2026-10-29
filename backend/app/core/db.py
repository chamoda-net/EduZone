from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from app.core.config import get_settings

_settings = get_settings()

# Two engines, two roles (CLAUDE.md section 5, rule 5).
# Tenant-facing code must only ever use AppSession; the tenant context
# (SET LOCAL app.tenant_id) is added in build step 2.
app_engine: AsyncEngine = create_async_engine(_settings.database_url, pool_pre_ping=True)
admin_engine: AsyncEngine = create_async_engine(_settings.admin_database_url, pool_pre_ping=True)

AppSession = async_sessionmaker(app_engine, expire_on_commit=False)
AdminSession = async_sessionmaker(admin_engine, expire_on_commit=False)


async def dispose_engines() -> None:
    await app_engine.dispose()
    await admin_engine.dispose()
