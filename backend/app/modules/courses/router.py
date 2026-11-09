from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.core.db import AppSession
from app.core.tenancy import TenantSession, site_url
from app.modules.auth.dependencies import CurrentUser, StaffActor
from app.modules.courses import certificates, reviews, service, student
from app.modules.courses.schemas import (
    CategoryOut,
    CertificateOut,
    CertificateVerify,
    MyReview,
    PublicReviewPage,
    ReplyIn,
    ReviewIn,
    StaffReview,
    CompletionOut,
    CourseCreate,
    CourseDetail,
    CourseRow,
    CourseUpdate,
    LearnCourse,
    LectureDetail,
    MyCourse,
    LectureCreate,
    LectureUpdate,
    SectionCreate,
    SectionUpdate,
)
from app.modules.learn import service as learn_service

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


# --- the student side (step C3), on any host like the rest of /learn -----------------------------

learn_router = APIRouter(prefix="/learn", tags=["learn"])


@learn_router.get("/courses", response_model=list[MyCourse])
async def my_courses(user: CurrentUser) -> list[MyCourse]:
    return await student.my_courses(user, await learn_service.memberships(user))


@learn_router.get("/courses/{course_id}", response_model=LearnCourse)
async def course_view(course_id: UUID, user: CurrentUser) -> LearnCourse:
    async with learn_service.in_tenant_of("class", course_id, user) as (session, auth, _):
        return await student.course_view(session, auth, course_id)


@learn_router.post("/courses/{course_id}/enroll", response_model=LearnCourse)
async def enroll(course_id: UUID, user: CurrentUser) -> LearnCourse:
    async with learn_service.in_tenant_of("class", course_id, user) as (session, auth, _):
        return await student.enroll(session, auth, course_id)


@learn_router.get("/lectures/{lecture_id}", response_model=LectureDetail)
async def lecture(lecture_id: UUID, user: CurrentUser) -> LectureDetail:
    async with learn_service.in_tenant_of("lesson", lecture_id, user) as (session, auth, _):
        return await student.lecture_detail(session, auth, lecture_id)


@learn_router.post("/lectures/{lecture_id}/complete", response_model=CompletionOut)
async def complete(lecture_id: UUID, user: CurrentUser) -> CompletionOut:
    async with learn_service.in_tenant_of("lesson", lecture_id, user) as (session, auth, _):
        return await student.set_completed(session, auth, lecture_id, True)


@learn_router.delete("/lectures/{lecture_id}/complete", response_model=CompletionOut)
async def uncomplete(lecture_id: UUID, user: CurrentUser) -> CompletionOut:
    async with learn_service.in_tenant_of("lesson", lecture_id, user) as (session, auth, _):
        return await student.set_completed(session, auth, lecture_id, False)


# --- reviews and certificates (step C4) ----------------------------------------------------------

@learn_router.get("/courses/{course_id}/review", response_model=MyReview | None)
async def my_review(course_id: UUID, user: CurrentUser) -> MyReview | None:
    async with learn_service.in_tenant_of("class", course_id, user) as (session, auth, _):
        return await reviews.my_review(session, auth, course_id)


@learn_router.put("/courses/{course_id}/review", response_model=MyReview)
async def save_review(course_id: UUID, body: ReviewIn, user: CurrentUser) -> MyReview:
    async with learn_service.in_tenant_of("class", course_id, user) as (session, auth, _):
        return await reviews.save_review(session, auth, course_id, body)


@learn_router.delete("/courses/{course_id}/review", status_code=204)
async def delete_review(course_id: UUID, user: CurrentUser) -> Response:
    async with learn_service.in_tenant_of("class", course_id, user) as (session, auth, _):
        await reviews.delete_review(session, auth, course_id)
    return Response(status_code=204)


@learn_router.get("/certificates", response_model=list[CertificateOut])
async def my_certificates(user: CurrentUser) -> list[CertificateOut]:
    return await certificates.my_certificates(user, await learn_service.memberships(user))


@public_router.get("/course/{slug}/reviews", response_model=PublicReviewPage)
async def course_reviews(slug: str, cursor: str | None = None,
                         limit: Annotated[int, Query(ge=1, le=50)] = 10) -> PublicReviewPage:
    return await reviews.public_reviews(slug, cursor, limit)


@public_router.get("/certificates/{number}", response_model=CertificateVerify)
async def verify_certificate(number: str) -> CertificateVerify:
    return await certificates.verify(number)


@public_router.get("/certificates/{number}/pdf")
async def certificate_pdf(number: str, request: Request) -> Response:
    c = await certificates.verify(number)
    if not c.valid:
        return Response(status_code=410)
    pdf = certificates.render_pdf(c, f"{await site_url(request)}/certificates/{c.certificate_no}")
    return Response(pdf, media_type="application/pdf", headers={
        "Content-Disposition": f'inline; filename="{c.certificate_no}.pdf"', "Cache-Control": "private, max-age=300"})


@org_router.get("/courses/{course_id}/reviews", response_model=list[StaffReview])
async def staff_course_reviews(course_id: UUID, session: TenantSession, actor: StaffActor) -> list[StaffReview]:
    return await reviews.course_reviews(session, actor, course_id)


@org_router.put("/course-reviews/{review_id}/reply", response_model=StaffReview)
async def reply(review_id: UUID, body: ReplyIn, session: TenantSession, actor: StaffActor) -> StaffReview:
    return await reviews.reply(session, actor, review_id, body)
