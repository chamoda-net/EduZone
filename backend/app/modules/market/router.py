from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.modules.auth.dependencies import CurrentUser
from app.modules.catalog.schemas import Exam, Medium
from app.modules.market import service
from app.modules.market.schemas import (
    Format,
    Home,
    InstituteOut,
    InstitutePage,
    MarketClass,
    MarketClassDetail,
    MarketClassPage,
    ProfileOut,
    ProfileUpdate,
    SitemapOut,
    Sort,
    SubjectOut,
    SubjectPage,
    TeacherOut,
    TeacherPage,
)

# The public marketplace: anyone, any host, no tenant. Public fields only (see service.py).
router = APIRouter(prefix="/market", tags=["market"])


@router.get("/home", response_model=Home)
async def home() -> Home:
    return await service.home()


@router.get("/subjects", response_model=list[SubjectOut])
async def subjects() -> list[SubjectOut]:
    return await service.subjects()


@router.get("/subjects/{slug}", response_model=SubjectPage)
async def subject_page(slug: str) -> SubjectPage:
    return await service.subject_page(slug)


@router.get("/classes", response_model=MarketClassPage)
async def classes(
    q: Annotated[str | None, Query(max_length=100)] = None,
    exam: Exam | None = None,
    subject: Annotated[str | None, Query(max_length=40)] = None,
    year: Annotated[int | None, Query(ge=2000, le=2100)] = None,
    medium: Medium | None = None,
    max_fee: Annotated[int | None, Query(ge=0)] = None,
    format: Format | None = None,
    sort: Sort = "popular",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=60)] = 24,
) -> MarketClassPage:
    return await service.search_classes(q=q, exam=exam, subject=subject, year=year, medium=medium, max_fee=max_fee,
                                        fmt=format, sort=sort, cursor=cursor, limit=limit)


@router.get("/classes/by-id/{class_id}", response_model=MarketClass)
async def class_by_id(class_id: UUID) -> MarketClass:
    """The public card (and canonical path) of a class, e.g. to link from the student area."""
    return await service.class_by_id(class_id)


@router.get("/classes/{subject_slug}/{teacher_slug}/{class_slug}", response_model=MarketClassDetail)
async def class_detail(subject_slug: str, teacher_slug: str, class_slug: str) -> MarketClassDetail:
    return await service.class_detail(subject_slug, teacher_slug, class_slug)


@router.get("/teachers", response_model=list[TeacherOut])
async def teachers(subject: Annotated[str | None, Query(max_length=40)] = None) -> list[TeacherOut]:
    return await service.teachers(subject)


@router.get("/teachers/{teacher_slug}", response_model=TeacherPage)
async def teacher_page(teacher_slug: str, subject: Annotated[str | None, Query(max_length=40)] = None) -> TeacherPage:
    return await service.teacher_page(teacher_slug, subject)


@router.get("/institutes", response_model=list[InstituteOut])
async def institutes() -> list[InstituteOut]:
    return await service.institutes()


@router.get("/institutes/{slug}", response_model=InstitutePage)
async def institute_page(slug: str) -> InstitutePage:
    return await service.institute_page(slug)


@router.get("/sitemap", response_model=SitemapOut)
async def sitemap() -> SitemapOut:
    return await service.sitemap()


# The signed-in teacher's own public profile (one per person, edited from any console).
me_router = APIRouter(prefix="/me", tags=["market"])


@me_router.get("/teacher-profile", response_model=ProfileOut)
async def my_profile(user: CurrentUser) -> ProfileOut:
    return await service.my_profile(user.user_id)


@me_router.put("/teacher-profile", response_model=ProfileOut)
async def update_profile(body: ProfileUpdate, user: CurrentUser) -> ProfileOut:
    return await service.update_profile(user.user_id, body)
