from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.core.tenancy import TenantSession
from app.modules.auth.dependencies import StaffActor
from app.modules.catalog import service
from app.modules.catalog.schemas import (
    ClassCreate,
    ClassOut,
    ClassPage,
    ClassStatus,
    ClassUpdate,
    LessonCreate,
    LessonOut,
    LessonUpdate,
    MonthCreate,
    MonthOut,
    MonthUpdate,
)

# Organization console (owners, admins, teachers).
org_router = APIRouter(tags=["org: catalog"])


# --- classes --------------------------------------------------------------------------

@org_router.get("/classes", response_model=ClassPage)
async def list_classes(
    session: TenantSession, actor: StaffActor,
    status: ClassStatus | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> ClassPage:
    return await service.list_classes(session, actor, status=status, cursor=cursor, limit=limit)


@org_router.post("/classes", response_model=ClassOut, status_code=201)
async def create_class(body: ClassCreate, session: TenantSession, actor: StaffActor) -> ClassOut:
    return await service.create_class(session, actor, body)


@org_router.get("/classes/{class_id}", response_model=ClassOut)
async def get_class(class_id: UUID, session: TenantSession, actor: StaffActor) -> ClassOut:
    return await service.get_class(session, actor, class_id)


@org_router.patch("/classes/{class_id}", response_model=ClassOut)
async def update_class(class_id: UUID, body: ClassUpdate, session: TenantSession, actor: StaffActor) -> ClassOut:
    return await service.update_class(session, actor, class_id, body)


@org_router.delete("/classes/{class_id}", status_code=204)
async def delete_class(class_id: UUID, session: TenantSession, actor: StaffActor) -> Response:
    await service.delete_class(session, actor, class_id)
    return Response(status_code=204)


# --- months ---------------------------------------------------------------------------

@org_router.get("/classes/{class_id}/months", response_model=list[MonthOut])
async def list_months(class_id: UUID, session: TenantSession, actor: StaffActor) -> list[MonthOut]:
    return await service.list_months(session, actor, class_id)


@org_router.post("/classes/{class_id}/months", response_model=MonthOut, status_code=201)
async def create_month(class_id: UUID, body: MonthCreate, session: TenantSession, actor: StaffActor) -> MonthOut:
    return await service.create_month(session, actor, class_id, body)


@org_router.patch("/months/{month_id}", response_model=MonthOut)
async def update_month(month_id: UUID, body: MonthUpdate, session: TenantSession, actor: StaffActor) -> MonthOut:
    return await service.update_month(session, actor, month_id, body)


@org_router.delete("/months/{month_id}", status_code=204)
async def delete_month(month_id: UUID, session: TenantSession, actor: StaffActor) -> Response:
    await service.delete_month(session, actor, month_id)
    return Response(status_code=204)


# --- lessons --------------------------------------------------------------------------

@org_router.get("/classes/{class_id}/lessons", response_model=list[LessonOut])
async def list_lessons(class_id: UUID, session: TenantSession, actor: StaffActor,
                       month_id: UUID | None = None) -> list[LessonOut]:
    return await service.list_lessons(session, actor, class_id, month_id)


@org_router.post("/classes/{class_id}/lessons", response_model=LessonOut, status_code=201)
async def create_lesson(class_id: UUID, body: LessonCreate, session: TenantSession,
                        actor: StaffActor) -> LessonOut:
    return await service.create_lesson(session, actor, class_id, body)


@org_router.patch("/lessons/{lesson_id}", response_model=LessonOut)
async def update_lesson(lesson_id: UUID, body: LessonUpdate, session: TenantSession,
                        actor: StaffActor) -> LessonOut:
    return await service.update_lesson(session, actor, lesson_id, body)


@org_router.delete("/lessons/{lesson_id}", status_code=204)
async def delete_lesson(lesson_id: UUID, session: TenantSession, actor: StaffActor) -> Response:
    await service.delete_lesson(session, actor, lesson_id)
    return Response(status_code=204)
