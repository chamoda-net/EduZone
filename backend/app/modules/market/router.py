from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query

from app.modules.auth.dependencies import CurrentUser
from app.modules.catalog.schemas import Exam, Medium
from app.modules.courses.schemas import Level
from app.modules.market import courses, service
from app.modules.market.schemas import (
    CourseCategoryOut,
    CourseCategoryPage,
    CourseLength,
    CoursePreviewIn,
    CoursePreviewOut,
    CoursePrice,
    CoursesHome,
    CourseSort,
    Format,
    Home,
    InstituteOut,
    InstitutePage,
    InstructorPage,
    MarketClass,
    MarketClassDetail,
    MarketClassPage,
    MarketCourseDetail,
    MarketCoursePage,
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
    out = await service.sitemap()
    out.courses, out.course_categories, out.instructors = await courses.sitemap_paths()
    return out


# --- courses (docs/COURSES.md, step C2) -----------------------------------------------------

@router.get("/courses", response_model=MarketCoursePage)
async def search_courses(
    q: Annotated[str | None, Query(max_length=100)] = None,
    category: Annotated[str | None, Query(max_length=40)] = None,
    level: Level | None = None,
    language: Medium | None = None,
    price: CoursePrice | None = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    rating: Annotated[float | None, Query(ge=0, le=5)] = None,
    length: CourseLength | None = None,
    sort: CourseSort = "popular",
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=60)] = 24,
) -> MarketCoursePage:
    return await courses.search_courses(q=q, category=category, level=level, language=language, price=price,
                                        max_price=max_price, rating=rating, length=length, sort=sort, cursor=cursor,
                                        limit=limit)


@router.get("/courses/home", response_model=CoursesHome)
async def courses_home() -> CoursesHome:
    return await courses.home()


@router.get("/courses/categories", response_model=list[CourseCategoryOut])
async def course_categories() -> list[CourseCategoryOut]:
    return await courses.categories()


@router.get("/courses/categories/{slug}", response_model=CourseCategoryPage)
async def course_category(slug: str) -> CourseCategoryPage:
    return await courses.category_page(slug)


@router.get("/course/{slug}", response_model=MarketCourseDetail)
async def course_detail(slug: str) -> MarketCourseDetail:
    return await courses.course_detail(slug)


@router.post("/course/{slug}/preview", response_model=CoursePreviewOut)
async def course_preview(slug: str, body: CoursePreviewIn) -> CoursePreviewOut:
    return await courses.preview(slug, body.lecture_id)


@router.get("/instructors/{slug}", response_model=InstructorPage)
async def instructor_page(slug: str) -> InstructorPage:
    return await courses.instructor_page(slug)


# The signed-in teacher's own public profile (one per person, edited from any console).
me_router = APIRouter(prefix="/me", tags=["market"])


@me_router.get("/teacher-profile", response_model=ProfileOut)
async def my_profile(user: CurrentUser) -> ProfileOut:
    return await service.my_profile(user.user_id)


@me_router.put("/teacher-profile", response_model=ProfileOut)
async def update_profile(body: ProfileUpdate, user: CurrentUser) -> ProfileOut:
    return await service.update_profile(user.user_id, body)
