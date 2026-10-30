"""The public marketplace: reads only through the public_* views (migration 0007), which expose
public fields of listed, active organizations and published classes. No tenant transaction and no
relaxed RLS: the views are owned by eduzone_admin and the app role can only SELECT them."""

import base64
import re
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AppSession
from app.core.errors import ApiError
from app.modules.market import profiles
from app.modules.market.schemas import (
    Format,
    Home,
    InstituteOut,
    InstitutePage,
    MarketClass,
    MarketClassDetail,
    MarketClassPage,
    MarketLesson,
    MarketMonth,
    ProfileOut,
    ProfileUpdate,
    SitemapOut,
    Sort,
    SubjectOut,
    SubjectPage,
    SubjectRef,
    TeacherCard,
    TeacherOut,
    TeacherPage,
)

_CARD_FIELDS = [f for f in MarketClass.model_fields if f != "path"]
_CARD = ", ".join(f"pc.{f}" for f in _CARD_FIELDS)


def _card(r: Any) -> MarketClass:
    data = {f: getattr(r, f) for f in _CARD_FIELDS}
    return MarketClass(**data, path=f"/{r.subject_slug}/{r.teacher_slug}/{r.slug}")


def _not_found(what: str) -> ApiError:
    return ApiError("NOT_FOUND", f"{what} not found.", status_code=404)


def _tsquery(q: str) -> str | None:
    """'phys kasu' -> 'phys:* & kasu:*' (prefix match on every word; letters and digits only)."""
    words = re.findall(r"[\w]+", q.lower())[:6]
    return " & ".join(f"{w}:*" for w in words) or None


# --- catalogue ------------------------------------------------------------------------------


async def search_classes(
    *, q: str | None = None, exam: str | None = None, subject: str | None = None, year: int | None = None,
    medium: str | None = None, max_fee: int | None = None, fmt: Format | None = None,
    teacher: str | None = None, org: str | None = None, sort: Sort = "popular", cursor: str | None = None,
    limit: int = 24,
) -> MarketClassPage:
    where = ["true"]
    params: dict[str, Any] = {}
    if q and (query := _tsquery(q)):
        where.append("pc.search @@ to_tsquery('simple', :q)")
        params["q"] = query
    for key, value, column in (("exam", exam, "exam"), ("subject", subject, "subject_slug"), ("year", year, "batch_year"),
                               ("medium", medium, "medium"), ("teacher", teacher, "teacher_slug"), ("org", org, "org_slug")):
        if value is not None:
            where.append(f"pc.{column} = :{key}")
            params[key] = value
    price = "COALESCE(pc.open_month_fee_cents, pc.monthly_fee_cents, pc.one_time_price_cents, 0)"
    if max_fee is not None:
        where.append(f"{price} <= :max_fee")
        params["max_fee"] = max_fee
    if fmt == "live":
        where.append("pc.has_live")
    elif fmt == "recorded":
        where.append("pc.has_recorded")
    order = {"popular": "pc.students DESC, pc.created_at DESC", "newest": "pc.created_at DESC",
             "price": f"{price} ASC, pc.students DESC"}[sort]
    offset = _decode_offset(cursor)
    sql_where = " AND ".join(where)
    async with AppSession() as session:
        total = (await session.execute(text(f"SELECT count(*) FROM public_classes pc WHERE {sql_where}"), params)).scalar_one()
        rows = (await session.execute(text(f"""
            SELECT {_CARD} FROM public_classes pc WHERE {sql_where}
            ORDER BY {order}, pc.id LIMIT :limit OFFSET :offset
        """), {**params, "limit": limit + 1, "offset": offset})).all()
    more = len(rows) > limit
    return MarketClassPage(items=[_card(r) for r in rows[:limit]], total=total,
                           next_cursor=_encode_offset(offset + limit) if more else None)


def _encode_offset(n: int) -> str:
    return base64.urlsafe_b64encode(str(n).encode()).decode().rstrip("=")


def _decode_offset(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        return max(0, min(int(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)).decode()), 10_000))
    except (ValueError, UnicodeDecodeError):
        raise ApiError("CURSOR_INVALID", "This page link is no longer valid.", status_code=400) from None


async def _subjects(session: AsyncSession, *, with_classes_only: bool = False) -> list[SubjectOut]:
    rows = (await session.execute(text(f"""
        SELECT id, slug, name, class_count, teacher_count FROM public_subjects
        {"WHERE class_count > 0" if with_classes_only else ""}
        ORDER BY class_count DESC, sort_order
    """))).all()
    return [SubjectOut(**r._mapping) for r in rows]


async def subjects() -> list[SubjectOut]:
    async with AppSession() as session:
        return await _subjects(session)


async def home() -> Home:
    async with AppSession() as session:
        subjects_ = await _subjects(session)
        popular = (await session.execute(text(f"""
            SELECT {_CARD} FROM public_classes pc ORDER BY pc.students DESC, pc.created_at DESC LIMIT 8
        """))).all()
        starting = (await session.execute(text(f"""
            SELECT {_CARD} FROM public_classes pc
            WHERE pc.open_month_start = date_trunc('month', now() AT TIME ZONE 'Asia/Colombo')::date
            ORDER BY pc.students DESC LIMIT 8
        """))).all()
        counts = (await session.execute(text("""
            SELECT (SELECT count(*) FROM public_classes) AS classes, (SELECT count(*) FROM public_teachers) AS teachers
        """))).one()
    return Home(subjects=subjects_, popular=[_card(r) for r in popular], starting=[_card(r) for r in starting],
                classes=counts.classes, teachers=counts.teachers)


# --- subjects, teachers, institutes --------------------------------------------------------


def _teacher(r: Any) -> TeacherOut:
    subjects_ = sorted(zip(r.subject_slugs or [], r.subject_names or [], strict=False), key=lambda s: s[1])
    return TeacherOut(slug=r.slug, display_name=r.display_name, headline=r.headline, bio=r.bio, photo_url=r.photo_url,
                      highlights=list(r.highlights or []), class_count=r.class_count, students=r.students or 0,
                      subjects=[SubjectRef(slug=s, name=n) for s, n in subjects_], mediums=sorted(r.mediums or []))


async def subject_page(slug: str) -> SubjectPage:
    async with AppSession() as session:
        s = (await session.execute(text(
            "SELECT id, slug, name, class_count, teacher_count FROM public_subjects WHERE slug = :s"), {"s": slug})).one_or_none()
        if s is None:
            raise _not_found("Subject")
        teachers = (await session.execute(text(
            "SELECT * FROM public_teachers WHERE :s = ANY (subject_slugs) ORDER BY students DESC, display_name"),
            {"s": slug})).all()
    classes = await search_classes(subject=slug, limit=48)
    return SubjectPage(subject=SubjectOut(**s._mapping), classes=classes.items, teachers=[_teacher(t) for t in teachers])


async def teachers(subject: str | None = None) -> list[TeacherOut]:
    async with AppSession() as session:
        rows = (await session.execute(text("""
            SELECT * FROM public_teachers WHERE CAST(:s AS text) IS NULL OR :s = ANY (subject_slugs)
            ORDER BY students DESC, display_name LIMIT 200
        """), {"s": subject})).all()
    return [_teacher(r) for r in rows]


async def teacher_page(teacher_slug: str, subject_slug: str | None) -> TeacherPage:
    async with AppSession() as session:
        r = (await session.execute(text("SELECT * FROM public_teachers WHERE slug = :t"), {"t": teacher_slug})).one_or_none()
    if r is None:
        raise _not_found("Teacher")
    teacher = _teacher(r)
    subject = next((s for s in teacher.subjects if s.slug == subject_slug), None)
    if subject_slug is not None and subject is None:
        raise _not_found("Teacher")          # they have no public class in that subject
    classes = await search_classes(teacher=teacher_slug, subject=subject_slug, limit=48)
    return TeacherPage(teacher=teacher, subject=subject, classes=classes.items,
                       other_subjects=[s for s in teacher.subjects if s.slug != subject_slug])


async def institutes() -> list[InstituteOut]:
    async with AppSession() as session:
        rows = (await session.execute(text("SELECT * FROM public_institutes ORDER BY class_count DESC, name"))).all()
    return [InstituteOut(slug=r.slug, name=r.name, logo_url=r.logo_url, class_count=r.class_count,
                         teacher_count=r.teacher_count, subjects=sorted(r.subject_names or [])) for r in rows]


async def institute_page(slug: str) -> InstitutePage:
    found = next((i for i in await institutes() if i.slug == slug), None)
    if found is None:
        raise _not_found("Institute")
    classes = await search_classes(org=slug, limit=96)
    return InstitutePage(institute=found, classes=classes.items)


# --- one class ------------------------------------------------------------------------------


async def class_detail(subject_slug: str, teacher_slug: str, class_slug: str) -> MarketClassDetail:
    async with AppSession() as session:
        r = (await session.execute(text(f"""
            SELECT {_CARD}, pc.description, pc.teacher_headline FROM public_classes pc
            WHERE pc.subject_slug = :s AND pc.teacher_slug = :t AND pc.slug = :c
            ORDER BY pc.students DESC LIMIT 1
        """), {"s": subject_slug, "t": teacher_slug, "c": class_slug})).one_or_none()
        if r is None:
            raise _not_found("Class")
        months = (await session.execute(text("""
            SELECT id, month_start, status, fee_cents, currency FROM public_class_months
            WHERE class_id = :c ORDER BY month_start
        """), {"c": r.id})).all()
        lessons = (await session.execute(text("""
            SELECT l.id, l.class_month_id, l.title, l.lesson_type, l.scheduled_at, l.duration_minutes, l.is_free_preview
            FROM public_lessons l LEFT JOIN public_class_months m ON m.id = l.class_month_id
            WHERE l.class_id = :c ORDER BY m.month_start NULLS FIRST, l.sort_order
        """), {"c": r.id})).all()
    return MarketClassDetail(
        klass=_card(r), description=r.description,
        teacher=TeacherCard(slug=r.teacher_slug, display_name=r.teacher_name, headline=r.teacher_headline,
                            photo_url=r.teacher_photo_url),
        months=[MarketMonth(**m._mapping) for m in months],
        lessons=[MarketLesson(**lesson._mapping) for lesson in lessons],
    )


async def class_by_id(class_id: UUID) -> MarketClass:
    async with AppSession() as session:
        r = (await session.execute(text(f"SELECT {_CARD} FROM public_classes pc WHERE pc.id = :id"),
                                   {"id": class_id})).one_or_none()
    if r is None:
        raise _not_found("Class")
    return _card(r)


async def sitemap() -> SitemapOut:
    async with AppSession() as session:
        subjects_ = (await session.execute(text("SELECT slug FROM public_subjects WHERE class_count > 0"))).scalars().all()
        pairs = (await session.execute(text(
            "SELECT DISTINCT subject_slug, teacher_slug FROM public_classes"))).all()
        classes = (await session.execute(text(
            "SELECT subject_slug, teacher_slug, slug FROM public_classes"))).all()
        orgs = (await session.execute(text("SELECT slug FROM public_institutes"))).scalars().all()
    return SitemapOut(subjects=list(subjects_), teachers=[f"/{p.subject_slug}/{p.teacher_slug}" for p in pairs],
                      classes=[f"/{c.subject_slug}/{c.teacher_slug}/{c.slug}" for c in classes],
                      institutes=[f"/institutes/{o}" for o in orgs])


# --- the teacher's own profile (console) ----------------------------------------------------


async def _profile_out(session: AsyncSession, user_id: UUID) -> ProfileOut:
    p = await profiles.get_profile(session, user_id)
    paths = (await session.execute(text("""
        SELECT DISTINCT subject_slug FROM public_classes WHERE teacher_slug = :slug ORDER BY 1
    """), {"slug": p.slug})).scalars().all()
    return ProfileOut(slug=p.slug, display_name=p.display_name, headline=p.headline, bio=p.bio, photo_url=p.photo_url,
                      highlights=list(p.highlights or []), public_paths=[f"/{s}/{p.slug}" for s in paths])


async def _require_teacher(session: AsyncSession, user_id: UUID) -> Any:
    if not (await session.execute(text("SELECT user_is_staff_anywhere(:u)"), {"u": user_id})).scalar_one():
        raise ApiError("ACCESS_DENIED", "Teacher profiles are for teachers and institute staff.", status_code=403)
    return (await session.execute(text("SELECT full_name FROM users WHERE id = :u"), {"u": user_id})).scalar_one()


async def my_profile(user_id: UUID) -> ProfileOut:
    async with AppSession() as session, session.begin():
        name = await _require_teacher(session, user_id)
        await profiles.ensure_for_user(session, user_id, name)
        return await _profile_out(session, user_id)


async def update_profile(user_id: UUID, body: ProfileUpdate) -> ProfileOut:
    if not profiles.valid_slug(body.slug):
        raise ApiError("SLUG_INVALID", "Use 3–40 lowercase letters, numbers and hyphens.", status_code=422)
    async with AppSession() as session, session.begin():
        name = await _require_teacher(session, user_id)
        await profiles.ensure_for_user(session, user_id, name)
        if await profiles.slug_taken(session, body.slug, except_user=user_id):
            raise ApiError("PROFILE_SLUG_TAKEN", "Another teacher already uses this link.", status_code=409)
        await session.execute(text("""
            UPDATE teacher_profiles SET slug = :slug, display_name = :name, headline = :headline, bio = :bio,
                   photo_url = :photo, highlights = :highlights
            WHERE user_id = :u
        """), {"u": user_id, "slug": body.slug, "name": " ".join(body.display_name.split()),
               "headline": (body.headline or "").strip() or None, "bio": (body.bio or "").strip() or None,
               "photo": str(body.photo_url) if body.photo_url else None, "highlights": body.highlights})
        return await _profile_out(session, user_id)
