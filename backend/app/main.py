from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel
from sqlalchemy import text

from app.core.db import AppSession, dispose_engines
from app.core.errors import install_error_handlers


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
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


app = FastAPI(title="EduZone API", version="0.1.0", lifespan=lifespan)
install_error_handlers(app)
app.include_router(api)
