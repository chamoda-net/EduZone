from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.core.tenancy import TenantSession
from app.modules.auth.dependencies import CurrentMember, StaffActor
from app.modules.catalog.schemas import Exam
from app.modules.learning import org, service
from app.modules.learning.schemas import (
    ClassStudent,
    GrantCreate,
    GrantInfo,
    GrantRevoke,
    LateRequestCreate,
    LateRequestDecision,
    LateRequestOut,
    LateRequestRow,
    MyClass,
    OpenResourceOut,
    PublicClassDetail,
    PublicClassPage,
    StudentClassView,
    StudentLessonDetail,
)

# --- public: anyone on the tenant's site ---------------------------------------------------

public_router = APIRouter(prefix="/public", tags=["public"])


@public_router.get("/classes", response_model=PublicClassPage)
async def list_classes(
    session: TenantSession,
    exam: Exam | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> PublicClassPage:
    return await service.list_published(session, exam=exam, cursor=cursor, limit=limit)


@public_router.get("/classes/{slug}", response_model=PublicClassDetail)
async def get_class(slug: str, session: TenantSession) -> PublicClassDetail:
    return await service.public_class(session, slug)


# --- student: signed in --------------------------------------------------------------------

student_router = APIRouter(prefix="/student", tags=["student"])


@student_router.get("/classes", response_model=list[MyClass])
async def my_classes(session: TenantSession, auth: CurrentMember) -> list[MyClass]:
    return await service.my_classes(session, auth)


@student_router.get("/classes/{slug}", response_model=StudentClassView)
async def class_view(slug: str, session: TenantSession, auth: CurrentMember) -> StudentClassView:
    return await service.class_view(session, auth, slug)


@student_router.post("/classes/{slug}/enroll", response_model=StudentClassView)
async def enroll(slug: str, session: TenantSession, auth: CurrentMember) -> StudentClassView:
    return await service.enroll(session, auth, slug)


@student_router.delete("/classes/{slug}/enroll", status_code=204)
async def leave(slug: str, session: TenantSession, auth: CurrentMember) -> Response:
    await service.leave(session, auth, slug)
    return Response(status_code=204)


@student_router.post("/months/{month_id}/late-request", response_model=LateRequestOut, status_code=201)
async def request_late_month(month_id: UUID, body: LateRequestCreate, session: TenantSession,
                             auth: CurrentMember) -> LateRequestOut:
    return await service.request_late_month(session, auth, month_id, body.note)


@student_router.get("/lessons/{lesson_id}", response_model=StudentLessonDetail)
async def lesson(lesson_id: UUID, session: TenantSession, auth: CurrentMember) -> StudentLessonDetail:
    return await service.lesson_detail(session, auth, lesson_id)


@student_router.post("/resources/{resource_id}/open", response_model=OpenResourceOut)
async def open_resource(resource_id: UUID, session: TenantSession, auth: CurrentMember) -> OpenResourceOut:
    return await service.open_resource(session, auth, resource_id)


# --- organization console --------------------------------------------------------------------

org_router = APIRouter(prefix="/org", tags=["org: students"])


@org_router.get("/classes/{class_id}/students", response_model=list[ClassStudent])
async def class_students(class_id: UUID, session: TenantSession, actor: StaffActor,
                         month_id: UUID | None = None) -> list[ClassStudent]:
    return await org.class_students(session, actor, class_id, month_id)


@org_router.post("/classes/{class_id}/grants", response_model=GrantInfo, status_code=201)
async def create_grant(class_id: UUID, body: GrantCreate, session: TenantSession, actor: StaffActor) -> GrantInfo:
    return await org.create_grant(session, actor, class_id, body)


@org_router.post("/grants/{grant_id}/revoke", status_code=204)
async def revoke_grant(grant_id: UUID, body: GrantRevoke, session: TenantSession, actor: StaffActor) -> Response:
    await org.revoke_grant(session, actor, grant_id, body.reason)
    return Response(status_code=204)


@org_router.get("/late-requests", response_model=list[LateRequestRow])
async def late_requests(session: TenantSession, actor: StaffActor,
                        status: Literal["pending", "approved", "rejected", "fulfilled"] = "pending",
                        ) -> list[LateRequestRow]:
    return await org.late_requests(session, actor, status)


@org_router.post("/late-requests/{request_id}/decision", response_model=LateRequestRow)
async def decide(request_id: UUID, body: LateRequestDecision, session: TenantSession,
                 actor: StaffActor) -> LateRequestRow:
    return await org.decide_late_request(session, actor, request_id, body)
