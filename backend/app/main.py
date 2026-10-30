from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from app.core.db import AppSession, dispose_engines
from app.core.errors import install_error_handlers
from app.integrations.bunny import close_bunny_http
from app.modules.auth.router import router as auth_router
from app.modules.catalog.router import org_router as catalog_org_router
from app.modules.checkout import router as checkout
from app.modules.learn.router import router as learn_router
from app.modules.learning import router as learning
from app.modules.market import router as market
from app.modules.ledger.router import org_router as ledger_org_router
from app.modules.media.router import org_router as media_org_router
from app.modules.media.router import webhook_router as media_webhook_router
from app.modules.platform.router import router as platform_router
from app.modules.tenants.router import public_router as tenants_public_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await close_bunny_http()
    await dispose_engines()


class HealthResponse(BaseModel):
    status: str
    database: str


api = APIRouter(prefix="/api/v1")


@api.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    async with AppSession() as session:
        await session.execute(text("SELECT 1"))
    return HealthResponse(status="ok", database="ok")


# Staff console. `/teach/{tenant_slug}/...` takes the tenant from the path (migration phase 3);
# the same routes under `/org/...` take it from the host (pre-migration tenant sites).
STAFF_ROUTERS = (catalog_org_router, media_org_router, learning.org_router, checkout.org_router, ledger_org_router)
for staff_router in STAFF_ROUTERS:
    api.include_router(staff_router, prefix="/teach/{tenant_slug}")
    api.include_router(staff_router, prefix="/org")

api.include_router(tenants_public_router)
api.include_router(auth_router)
api.include_router(learn_router)
api.include_router(market.router)
api.include_router(market.me_router)
api.include_router(media_webhook_router)
api.include_router(learning.public_router)
api.include_router(learning.student_router)
api.include_router(checkout.student_router)
api.include_router(checkout.webhook_router)
api.include_router(checkout.dev_router)
api.include_router(platform_router)


app = FastAPI(title="EduZone API", version="0.1.0", lifespan=lifespan)
install_error_handlers(app)
app.include_router(api)
