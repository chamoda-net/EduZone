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
from app.modules.learning import router as learning
from app.modules.media.router import org_router as media_org_router
from app.modules.media.router import webhook_router as media_webhook_router
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


api.include_router(tenants_public_router)
api.include_router(auth_router)
api.include_router(catalog_org_router)
api.include_router(media_org_router)
api.include_router(media_webhook_router)
api.include_router(learning.public_router)
api.include_router(learning.student_router)
api.include_router(learning.org_router)
api.include_router(checkout.student_router)
api.include_router(checkout.org_router)
api.include_router(checkout.webhook_router)
api.include_router(checkout.dev_router)


app = FastAPI(title="EduZone API", version="0.1.0", lifespan=lifespan)
install_error_handlers(app)
app.include_router(api)
