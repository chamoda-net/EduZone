from uuid import UUID

from fastapi import APIRouter, Response

from app.core.db import AppSession
from app.core.tenancy import TenantSession
from app.modules.auth.dependencies import StaffActor
from app.modules.courses import service
from app.modules.courses.schemas import (
    CategoryOut,
    CourseCreate,
    CourseDetail,
    CourseRow,
    CourseUpdate,
    LectureCreate,
    LectureUpdate,
    SectionCreate,
    SectionUpdate,
)

# Course builder in the organization console (owners, admins, teachers).
org_router = APIRouter(tags=["org: courses"])

# Course categories are public catalogue data (EduZone-managed).
public_router = APIRouter(prefix="/market", tags=["market"])


@public_router.get("/course-categories", response_model=list[CategoryOut])
async def categories() -> list[CategoryOut]:
    async with AppSession() as s:
        return [CategoryOut.model_validate(c) for c in await service.categories(s)]


@org_router.get("/courses", response_model=list[CourseRow])
async def list_courses(session: TenantSession, actor: StaffActor) -> list[CourseRow]:
    return await service.list_courses(session, actor)


@org_router.post("/courses", response_model=CourseDetail, status_code=201)
async def create_course(body: CourseCreate, session: TenantSession, actor: StaffActor) -> CourseDetail:
    return await service.create_course(session, actor, body)


@org_router.get("/courses/{course_id}", response_model=CourseDetail)
async def get_course(course_id: UUID, session: TenantSession, actor: StaffActor) -> CourseDetail:
    return await service.get_course(session, actor, course_id)


@org_router.patch("/courses/{course_id}", response_model=CourseDetail)
async def update_course(course_id: UUID, body: CourseUpdate, session: TenantSession,
                        actor: StaffActor) -> CourseDetail:
    return await service.update_course(session, actor, course_id, body)


@org_router.delete("/courses/{course_id}", status_code=204)
async def delete_course(course_id: UUID, session: TenantSession, actor: StaffActor) -> Response:
    await service.delete_course(session, actor, course_id)
    return Response(status_code=204)


@org_router.post("/courses/{course_id}/submit", response_model=CourseDetail)
async def submit(course_id: UUID, session: TenantSession, actor: StaffActor) -> CourseDetail:
    return await service.submit(session, actor, course_id)


@org_router.post("/courses/{course_id}/withdraw", response_model=CourseDetail)
async def withdraw(course_id: UUID, session: TenantSession, actor: StaffActor) -> CourseDetail:
    return await service.withdraw(session, actor, course_id)


@org_router.post("/courses/{course_id}/unpublish", response_model=CourseDetail)
async def unpublish(course_id: UUID, session: TenantSession, actor: StaffActor) -> CourseDetail:
    return await service.unpublish(session, actor, course_id)


@org_router.post("/courses/{course_id}/sections", response_model=CourseDetail, status_code=201)
async def create_section(course_id: UUID, body: SectionCreate, session: TenantSession,
                         actor: StaffActor) -> CourseDetail:
    return await service.create_section(session, actor, course_id, body)


@org_router.patch("/course-sections/{section_id}", response_model=CourseDetail)
async def update_section(section_id: UUID, body: SectionUpdate, session: TenantSession,
                         actor: StaffActor) -> CourseDetail:
    return await service.update_section(session, actor, section_id, body)


@org_router.delete("/course-sections/{section_id}", response_model=CourseDetail)
async def delete_section(section_id: UUID, session: TenantSession, actor: StaffActor) -> CourseDetail:
    return await service.delete_section(session, actor, section_id)


@org_router.post("/course-sections/{section_id}/lectures", response_model=CourseDetail, status_code=201)
async def create_lecture(section_id: UUID, body: LectureCreate, session: TenantSession,
                         actor: StaffActor) -> CourseDetail:
    return await service.create_lecture(session, actor, section_id, body)


@org_router.patch("/lectures/{lecture_id}", response_model=CourseDetail)
async def update_lecture(lecture_id: UUID, body: LectureUpdate, session: TenantSession,
                         actor: StaffActor) -> CourseDetail:
    return await service.update_lecture(session, actor, lecture_id, body)


@org_router.delete("/lectures/{lecture_id}", response_model=CourseDetail)
async def delete_lecture(lecture_id: UUID, session: TenantSession, actor: StaffActor) -> CourseDetail:
    return await service.delete_lecture(session, actor, lecture_id)
