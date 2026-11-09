"""Courses on the public marketplace (docs/COURSES.md, step C2): the catalogue, category pages, the course landing
page, instructor pages and the free previews. Reads only through the public course views (migration 0011), like
the tuition marketplace; a preview's signed URL is the one exception that needs the course's tenant, and it only
ever signs a promo video or a published free-preview lecture of a public course."""

from typing import Any
from uuid import UUID

from sqlalchemy import text

from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.tenancy import tenant_transaction
from app.modules.market.schemas import (
    CourseCategoryOut,
    CourseCategoryPage,
    CourseLectureOut,
    CourseLength,
    CoursePreviewOut,
    CoursePrice,
    CourseSectionOut,
    CourseSort,
    CoursesHome,
    InstructorOut,
    InstructorPage,
    MarketCourse,
    MarketCourseDetail,
    MarketCoursePage,
)
from app.modules.market.service import _decode_offset, _encode_offset, _not_found, _tsquery, search_classes
from app.modules.media import repository as media_repo
from app.modules.media.service import signed_url

_CARD_FIELDS = [f for f in MarketCourse.model_fields if f != "path"]
_CARD = ", ".join(f"pc.{f}" for f in _CARD_FIELDS)

_LENGTHS: dict[str, tuple[int, int | None]] = {
    "short": (0, 2 * 3600), "medium": (2 * 3600, 6 * 3600), "long": (6 * 3600, 17 * 3600), "extra": (17 * 3600, None),
}
_ORDER = {
    "popular": "pc.students DESC, pc.rating_avg DESC NULLS LAST, pc.first_published_at DESC",
    "rating": "pc.rating_avg DESC NULLS LAST, pc.rating_count DESC, pc.students DESC",
    "newest": "pc.first_published_at DESC NULLS LAST",
    "price_low": "COALESCE(pc.one_time_price_cents, 0) ASC, pc.students DESC",
    "price_high": "COALESCE(pc.one_time_price_cents, 0) DESC, pc.students DESC",
}


def _card(r: Any) -> MarketCourse:
    data = {f: getattr(r, f) for f in _CARD_FIELDS}
    data["rating_avg"] = float(r.rating_avg) if r.rating_avg is not None else None
    return MarketCourse(**data, path=f"/course/{r.slug}")


def _category(r: Any) -> CourseCategoryOut:
    return CourseCategoryOut.model_validate(dict(r._mapping))


def _instructor(r: Any) -> InstructorOut:
    return InstructorOut(slug=r.slug, display_name=r.display_name, headline=r.headline, bio=r.bio,
                         photo_url=r.photo_url, highlights=list(r.highlights or []), course_count=r.course_count,
                         class_count=r.class_count, students=int(r.students or 0),
                         rating_avg=float(r.rating_avg) if r.rating_avg is not None else None)


# --- catalogue ------------------------------------------------------------------------------

async def search_courses(
    *, q: str | None = None, category: str | None = None, level: str | None = None, language: str | None = None,
    price: CoursePrice | None = None, max_price: int | None = None, rating: float | None = None,
    length: CourseLength | None = None, teacher: str | None = None, sort: CourseSort = "popular",
    cursor: str | None = None, limit: int = 24,
) -> MarketCoursePage:
    where = ["true"]
    params: dict[str, Any] = {}
    if q and (query := _tsquery(q)):
        where.append("pc.search @@ to_tsquery('simple', :q)")
        params["q"] = query
    if category:
        # A top-level category includes its subcategories.
        where.append("(pc.category_slug = :category OR pc.parent_category_slug = :category)")
        params["category"] = category
    for key, value, column in (("level", level, "level"), ("language", language, "language"),
                               ("teacher", teacher, "teacher_slug")):
        if value is not None:
            where.append(f"pc.{column} = :{key}")
            params[key] = value
    if price == "free":
        where.append("pc.pricing_model = 'free'")
    elif price == "paid":
        where.append("pc.pricing_model = 'one_time'")
    if max_price is not None:
        where.append("COALESCE(pc.one_time_price_cents, 0) <= :max_price")
        params["max_price"] = max_price
    if rating is not None:
        where.append("pc.rating_avg >= :rating")
        params["rating"] = rating
    if length is not None:
        low, high = _LENGTHS[length]
        where.append("pc.total_video_seconds >= :len_low")
        params["len_low"] = low
        if high is not None:
            where.append("pc.total_video_seconds < :len_high")
            params["len_high"] = high
    offset = _decode_offset(cursor)
    sql_where = " AND ".join(where)
    async with AppSession() as session:
        total = (await session.execute(text(f"SELECT count(*) FROM public_courses pc WHERE {sql_where}"),
                                       params)).scalar_one()
        rows = (await session.execute(text(f"""
            SELECT {_CARD} FROM public_courses pc WHERE {sql_where}
            ORDER BY {_ORDER[sort]}, pc.id LIMIT :limit OFFSET :offset
        """), {**params, "limit": limit + 1, "offset": offset})).all()
    more = len(rows) > limit
    return MarketCoursePage(items=[_card(r) for r in rows[:limit]], total=total,
                            next_cursor=_encode_offset(offset + limit) if more else None)


async def categories() -> list[CourseCategoryOut]:
    async with AppSession() as session:
        rows = (await session.execute(text("""
            SELECT id, parent_id, slug, name_en, name_si, name_ta, course_count FROM public_course_categories
            ORDER BY parent_id NULLS FIRST, sort_order, name_en
        """))).all()
    return [_category(r) for r in rows]


async def category_page(slug: str) -> CourseCategoryPage:
    found = await categories()
    category = next((c for c in found if c.slug == slug), None)
    if category is None:
        raise _not_found("Category")
    parent = next((c for c in found if c.id == category.parent_id), None)
    return CourseCategoryPage(category=category, parent=parent,
                              children=[c for c in found if c.parent_id == category.id])


async def home() -> CoursesHome:
    async with AppSession() as session:
        async def lane(order: str, where: str = "true") -> list[MarketCourse]:
            rows = (await session.execute(text(
                f"SELECT {_CARD} FROM public_courses pc WHERE {where} ORDER BY {order}, pc.id LIMIT 8"))).all()
            return [_card(r) for r in rows]

        popular = await lane(_ORDER["popular"])
        newest = await lane(_ORDER["newest"])
        top_rated = await lane(_ORDER["rating"], "pc.rating_avg IS NOT NULL")
        total = (await session.execute(text("SELECT count(*) FROM public_courses"))).scalar_one()
    tops = [c for c in await categories() if c.parent_id is None]
    return CoursesHome(categories=sorted(tops, key=lambda c: -c.course_count), popular=popular, newest=newest,
                       top_rated=top_rated, total=total)


# --- one course -----------------------------------------------------------------------------

async def _instructor_row(session: Any, slug: str) -> Any:
    return (await session.execute(text("SELECT * FROM public_instructors WHERE slug = :s"), {"s": slug})).one_or_none()


async def course_detail(slug: str) -> MarketCourseDetail:
    async with AppSession() as session:
        r = (await session.execute(text(f"""
            SELECT {_CARD}, pc.description, pc.learning_objectives, pc.requirements, pc.target_audience, pc.has_promo
            FROM public_courses pc WHERE pc.slug = :s
        """), {"s": slug})).one_or_none()
        if r is None:
            raise _not_found("Course")
        sections = (await session.execute(text("""
            SELECT id, title FROM public_course_sections WHERE course_id = :c ORDER BY sort_order, id
        """), {"c": r.id})).all()
        lectures = (await session.execute(text("""
            SELECT id, section_id, title, lesson_type, is_free_preview, video_seconds FROM public_course_lectures
            WHERE course_id = :c ORDER BY sort_order, id
        """), {"c": r.id})).all()
        instructor = await _instructor_row(session, r.teacher_slug)
    by_section: dict[UUID, list[CourseLectureOut]] = {s.id: [] for s in sections}
    for lec in lectures:
        by_section.setdefault(lec.section_id, []).append(CourseLectureOut(
            id=lec.id, title=lec.title, lesson_type=lec.lesson_type, is_free_preview=lec.is_free_preview,
            video_seconds=lec.video_seconds, can_preview=lec.is_free_preview and lec.video_seconds > 0))
    outline = [CourseSectionOut(id=s.id, title=s.title, lectures=by_section[s.id],
                                video_seconds=sum(x.video_seconds for x in by_section[s.id]))
               for s in sections if by_section[s.id]]
    return MarketCourseDetail(
        course=_card(r), description=r.description, learning_objectives=list(r.learning_objectives),
        requirements=list(r.requirements), target_audience=list(r.target_audience), has_promo=r.has_promo,
        sections=outline, instructor=_instructor(instructor),
    )


async def preview(slug: str, lecture_id: UUID | None) -> CoursePreviewOut:
    """A signed stream of the promo video or of a published free-preview lecture, for anyone. No view is counted
    and no watermark is shown: these are the parts the instructor chose to show to everyone."""
    async with AppSession() as session:
        c = (await session.execute(text("SELECT id, tenant_id, title FROM public_courses WHERE slug = :s"),
                                   {"s": slug})).one_or_none()
        if c is None:
            raise _not_found("Course")
        title = c.title
        if lecture_id is not None:
            lec = (await session.execute(text("""
                SELECT id, title FROM public_course_lectures
                WHERE id = :l AND course_id = :c AND is_free_preview AND video_seconds > 0
            """), {"l": lecture_id, "c": c.id})).one_or_none()
            if lec is None:
                raise ApiError("NOT_FOUND", "This lecture has no free preview.", status_code=404)
            title = lec.title
    async with tenant_transaction(c.tenant_id) as session:
        if lecture_id is None:
            asset_id = (await session.execute(text("""
                SELECT a.id FROM classes cl JOIN media_assets a ON a.id = cl.promo_media_id
                WHERE cl.id = :c AND a.kind = 'video' AND a.status = 'ready'
            """), {"c": c.id})).scalar_one_or_none()
        else:
            asset_id = (await session.execute(text("""
                SELECT a.id FROM lesson_resources r JOIN media_assets a ON a.id = r.media_asset_id
                WHERE r.lesson_id = :l AND a.kind = 'video' AND a.status = 'ready'
                ORDER BY r.sort_order, r.created_at LIMIT 1
            """), {"l": lecture_id})).scalar_one_or_none()
        if asset_id is None:
            raise ApiError("NOT_FOUND", "There is no preview video.", status_code=404)
        asset = await media_repo.get_asset(session, asset_id)
        assert asset is not None
        url = await signed_url(session, asset)
    return CoursePreviewOut(url=url.url, expires_at=url.expires_at, playback=url.playback, title=title)


# --- instructors ----------------------------------------------------------------------------

async def instructor_page(slug: str) -> InstructorPage:
    async with AppSession() as session:
        r = await _instructor_row(session, slug)
    if r is None:
        raise _not_found("Instructor")
    courses = await search_courses(teacher=slug, limit=60)
    classes = await search_classes(teacher=slug, limit=60)
    return InstructorPage(instructor=_instructor(r), courses=courses.items, classes=classes.items)


async def sitemap_paths() -> tuple[list[str], list[str], list[str]]:
    async with AppSession() as session:
        courses = (await session.execute(text("SELECT slug FROM public_courses"))).scalars().all()
        instructors = (await session.execute(text("SELECT slug FROM public_instructors"))).scalars().all()
    cats = await categories()
    by_id = {c.id: c for c in cats}
    category_paths = [f"/courses/{by_id[c.parent_id].slug}/{c.slug}" if c.parent_id in by_id else f"/courses/{c.slug}"
                      for c in cats if c.course_count > 0]
    return ([f"/course/{s}" for s in courses], category_paths, [f"/instructor/{s}" for s in instructors])
