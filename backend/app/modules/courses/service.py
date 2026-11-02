"""Courses (docs/COURSES.md, step C1): the course builder in the organization console.

A course is a `classes` row with kind = 'course': landing page, intended learners, pricing (one-time or free),
messages, and a curriculum of sections and lectures (`lessons` with section_id). Lecture files reuse the media
module's lesson resources (`/lessons/{id}/resources`).

Status: draft -> in_review (first publish only; EduZone staff approve) -> published <-> archived. After the first
approval, publishing again needs no review. While in review the course is locked; the instructor may withdraw it.
Permissions follow classes: owners and admins manage every course, a teacher only the courses they teach, and a
course the caller may not manage is a 404.
"""

import re
import secrets
import unicodedata
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.errors import ApiError
from app.modules.auth.dependencies import Actor
from app.modules.catalog.service import _check_teacher, _delete_or_conflict
from app.modules.courses.schemas import (
    Check,
    CourseCreate,
    CourseDetail,
    CourseRow,
    CourseUpdate,
    LectureCreate,
    LectureOut,
    LectureUpdate,
    SectionCreate,
    SectionOut,
    SectionUpdate,
)
from app.modules.market import profiles

# Udemy's minimums, adapted (docs/COURSES.md section 7).
MIN_LECTURES = 5
MIN_VIDEO_SECONDS = 30 * 60
MIN_DESCRIPTION_WORDS = 100
MIN_OBJECTIVES = 4

_ROW = """
    SELECT c.*, t.currency, COALESCE(NULLIF(tm.display_name, ''), u.full_name) AS teacher_name
    FROM classes c
    JOIN tenants t ON t.id = c.tenant_id
    JOIN tenant_members tm ON tm.id = c.teacher_member_id
    JOIN users u ON u.id = tm.user_id
    WHERE c.kind = 'course'
"""


def _not_found() -> ApiError:
    return ApiError("NOT_FOUND", "Course not found.", status_code=404)


async def _audit(session: AsyncSession, actor: Actor, action: str, entity_type: str, entity_id: UUID,
                 details: dict[str, Any] | None = None) -> None:
    await write_audit(session, actor_user_id=actor.auth.user_id, action=action, entity_type=entity_type,
                      entity_id=entity_id, details=details, ip=actor.ip)


def _row(r: Any) -> CourseRow:
    return CourseRow.model_validate({k: getattr(r, k) for k in CourseRow.model_fields})


async def _load(session: AsyncSession, actor: Actor, course_id: UUID, *, for_update: bool = False) -> Any:
    if for_update:
        # Lock the row first (FOR UPDATE can't sit on the joined query's outer side cleanly).
        await session.execute(text("SELECT 1 FROM classes WHERE id = :id AND kind = 'course' FOR UPDATE"),
                              {"id": course_id})
    r = (await session.execute(text(_ROW + " AND c.id = :id"), {"id": course_id})).one_or_none()
    if r is None or not (actor.manages_all or r.teacher_member_id == actor.auth.member_id):
        raise _not_found()
    return r


def _editable(c: Any) -> None:
    if c.status == "in_review":
        raise ApiError("COURSE_IN_REVIEW", "This course is being reviewed. Withdraw it to make changes.",
                       status_code=409)


# --- slugs --------------------------------------------------------------------------------

def _slugify(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")[:60].strip("-") or "course"


async def _slug_taken(session: AsyncSession, slug: str, exclude: UUID | None = None) -> bool:
    """Course slugs are unique on the whole marketplace (/course/<slug>), and within the tenant across classes."""
    taken = (await session.execute(text("SELECT course_slug_taken(:s, :x)"), {"s": slug, "x": exclude})).scalar_one()
    if taken:
        return True
    return (await session.execute(text("SELECT EXISTS (SELECT 1 FROM classes WHERE slug = :s AND id IS DISTINCT FROM :x)"),
                                  {"s": slug, "x": exclude})).scalar_one()


async def _unique_slug(session: AsyncSession, title: str) -> str:
    base = slug = _slugify(title)
    while await _slug_taken(session, slug):
        slug = f"{base}-{secrets.token_hex(2)}"
    return slug


# --- reads ----------------------------------------------------------------------------------

async def list_courses(session: AsyncSession, actor: Actor) -> list[CourseRow]:
    rows = (await session.execute(text(_ROW + """
        AND (CAST(:teacher AS uuid) IS NULL OR c.teacher_member_id = :teacher)
        ORDER BY c.updated_at DESC, c.id DESC
    """), {"teacher": None if actor.manages_all else actor.auth.member_id})).all()
    return [_row(r) for r in rows]


async def _curriculum(session: AsyncSession, course_id: UUID) -> list[SectionOut]:
    sections = (await session.execute(text("""
        SELECT id, title, sort_order FROM course_sections WHERE class_id = :c ORDER BY sort_order, created_at
    """), {"c": course_id})).all()
    lectures = (await session.execute(text("""
        SELECT l.id, l.section_id, l.title, l.description, l.lesson_type, l.article_body, l.sort_order,
               l.is_free_preview, l.is_published,
               COALESCE(sum(a.duration_seconds) FILTER (WHERE a.kind = 'video' AND a.status = 'ready'), 0)::int
                   AS video_seconds,
               count(r.id)::int AS files,
               count(r.id) FILTER (WHERE a.kind = 'video' AND a.status <> 'ready')::int AS pending_videos
        FROM lessons l
        LEFT JOIN lesson_resources r ON r.lesson_id = l.id
        LEFT JOIN media_assets a ON a.id = r.media_asset_id
        WHERE l.class_id = :c AND l.section_id IS NOT NULL
        GROUP BY l.id
        ORDER BY l.sort_order, l.created_at
    """), {"c": course_id})).all()
    by_section: dict[UUID, list[LectureOut]] = {s.id: [] for s in sections}
    for lec in lectures:
        by_section.setdefault(lec.section_id, []).append(
            LectureOut.model_validate({k: getattr(lec, k) for k in LectureOut.model_fields}))
    return [SectionOut(id=s.id, title=s.title, sort_order=s.sort_order, lectures=by_section[s.id]) for s in sections]


def _words(text_: str | None) -> int:
    return len((text_ or "").split())


async def run_checks(session: AsyncSession, c: Any, sections: list[SectionOut]) -> list[Check]:
    """Everything a course needs before it can be submitted (docs/COURSES.md section 7). Runs in the course's
    tenant transaction (or an admin transaction with app.tenant_id set)."""
    published = [lec for s in sections for lec in s.lectures if lec.is_published]
    video_seconds = sum(lec.video_seconds for lec in published)
    tenant_status = (await session.execute(text("SELECT status FROM tenants WHERE id = :t"),
                                           {"t": c.tenant_id})).scalar_one()
    category_ok = c.category_id is not None and bool((await session.execute(
        text("SELECT is_active FROM course_categories WHERE id = :id"), {"id": c.category_id})).scalar())
    profile = (await session.execute(text("""
        SELECT tp.photo_url, tp.bio FROM tenant_members m JOIN teacher_profiles tp ON tp.user_id = m.user_id
        WHERE m.id = :m
    """), {"m": c.teacher_member_id})).one_or_none()
    return [
        Check(key="tenant_approved", ok=tenant_status == "active"),
        Check(key="subtitle", ok=bool((c.subtitle or "").strip())),
        Check(key="description", ok=_words(c.description) >= MIN_DESCRIPTION_WORDS,
              current=_words(c.description), required=MIN_DESCRIPTION_WORDS),
        Check(key="cover", ok=bool(c.cover_image_url)),
        Check(key="category", ok=category_ok),
        Check(key="level", ok=c.level is not None),
        Check(key="language", ok=c.medium is not None),
        Check(key="objectives", ok=len(c.learning_objectives) >= MIN_OBJECTIVES,
              current=len(c.learning_objectives), required=MIN_OBJECTIVES),
        Check(key="requirements", ok=len(c.requirements) >= 1, current=len(c.requirements), required=1),
        Check(key="audience", ok=len(c.target_audience) >= 1, current=len(c.target_audience), required=1),
        Check(key="price", ok=c.pricing_model == "free" or (c.one_time_price_cents or 0) > 0),
        Check(key="lectures", ok=len(published) >= MIN_LECTURES, current=len(published), required=MIN_LECTURES),
        Check(key="video_minutes", ok=video_seconds >= MIN_VIDEO_SECONDS,
              current=video_seconds // 60, required=MIN_VIDEO_SECONDS // 60),
        Check(key="videos_ready", ok=all(lec.pending_videos == 0 for lec in published),
              current=sum(lec.pending_videos for lec in published), required=0),
        Check(key="instructor_profile",
              ok=profile is not None and bool(profile.photo_url) and bool((profile.bio or "").strip())),
    ]


async def detail_of(session: AsyncSession, c: Any) -> CourseDetail:
    """The full builder view of a loaded course row (shared with the platform admin's review)."""
    sections = await _curriculum(session, c.id)
    checks = await run_checks(session, c, sections)
    base = {k: getattr(c, k) for k in CourseDetail.model_fields
            if k not in ("sections", "checks", "ready_to_submit", "needs_review", "tenant_name")}
    return CourseDetail(**base, sections=sections, checks=checks, ready_to_submit=all(x.ok for x in checks),
                        needs_review=c.first_published_at is None)


async def get_course(session: AsyncSession, actor: Actor, course_id: UUID) -> CourseDetail:
    return await detail_of(session, await _load(session, actor, course_id))


async def refresh_stats(session: AsyncSession, course_id: UUID) -> None:
    """Lecture count and video length shown on the marketplace: published lectures, ready videos."""
    await session.execute(text("""
        UPDATE classes c SET
            lecture_count = (SELECT count(*) FROM lessons l
                             WHERE l.class_id = c.id AND l.section_id IS NOT NULL AND l.is_published),
            total_video_seconds = COALESCE((
                SELECT sum(a.duration_seconds) FROM lessons l
                JOIN lesson_resources r ON r.lesson_id = l.id
                JOIN media_assets a ON a.id = r.media_asset_id AND a.kind = 'video' AND a.status = 'ready'
                WHERE l.class_id = c.id AND l.section_id IS NOT NULL AND l.is_published), 0)
        WHERE c.id = :id AND c.kind = 'course'
    """), {"id": course_id})


# --- course ---------------------------------------------------------------------------------

async def _check_category(session: AsyncSession, category_id: int) -> None:
    ok = (await session.execute(text("SELECT is_active FROM course_categories WHERE id = :id"),
                                {"id": category_id})).scalar()
    if not ok:
        raise ApiError("CATEGORY_INVALID", "Choose a category from the list.", status_code=422)


async def create_course(session: AsyncSession, actor: Actor, body: CourseCreate) -> CourseDetail:
    teacher = body.teacher_member_id or actor.auth.member_id
    await _check_teacher(session, actor, teacher)
    if body.category_id is not None:
        await _check_category(session, body.category_id)
    slug = await _unique_slug(session, body.title)
    try:
        async with session.begin_nested():
            course_id = (await session.execute(text("""
                INSERT INTO classes (tenant_id, kind, teacher_member_id, title, slug, category_id, pricing_model,
                                     allow_late_months, status)
                VALUES (current_tenant_id(), 'course', :teacher, :title, :slug, :cat, 'free', false, 'draft')
                RETURNING id
            """), {"teacher": teacher, "title": body.title.strip(), "slug": slug,
                   "cat": body.category_id})).scalar_one()
    except IntegrityError as exc:       # a race for the same slug on another tenant
        raise ApiError("SLUG_TAKEN", "Another course already uses this address. Try again.", status_code=409) from exc
    await _audit(session, actor, "course.create", "class", course_id, {"title": body.title, "slug": slug})
    return await get_course(session, actor, course_id)


async def update_course(session: AsyncSession, actor: Actor, course_id: UUID, body: CourseUpdate) -> CourseDetail:
    c = await _load(session, actor, course_id, for_update=True)
    _editable(c)
    changes = {k: v for k, v in body.changes().items() if getattr(c, k) != v}
    if not changes:
        return await detail_of(session, c)

    if "teacher_member_id" in changes:
        if not actor.manages_all:
            raise ApiError("ACCESS_DENIED", "Only owners and admins can reassign a course.", status_code=403)
        await _check_teacher(session, actor, changes["teacher_member_id"])
    if "slug" in changes:
        if c.first_published_at is not None:
            raise ApiError("SLUG_LOCKED", "A published course keeps its address.", status_code=409)
        if await _slug_taken(session, changes["slug"], exclude=c.id):
            raise ApiError("SLUG_TAKEN", "Another course already uses this address.", status_code=409)
    if changes.get("category_id") is not None:
        await _check_category(session, changes["category_id"])
    if changes.get("subject_id") is not None and not (await session.execute(
            text("SELECT is_active FROM subjects WHERE id = :id"), {"id": changes["subject_id"]})).scalar():
        raise ApiError("SUBJECT_INVALID", "Choose a subject from the list.", status_code=422)
    if changes.get("promo_media_id") is not None and not (await session.execute(text("""
            SELECT 1 FROM media_assets WHERE id = :id AND kind = 'video' AND status NOT IN ('deleted', 'failed')
        """), {"id": changes["promo_media_id"]})).first():
        raise ApiError("MEDIA_INVALID", "The promo video must be one of your videos.", status_code=422)
    pricing = changes.get("pricing_model", c.pricing_model)
    price = changes.get("one_time_price_cents", c.one_time_price_cents)
    if pricing == "one_time" and not price:
        raise ApiError("PRICING_INVALID", "A paid course needs a price.", status_code=422)

    sets = ", ".join(f"{k} = :{k}" for k in changes)
    try:
        async with session.begin_nested():
            await session.execute(text(f"UPDATE classes SET {sets}, updated_at = now() WHERE id = :id"),
                                  {**changes, "id": c.id})
    except IntegrityError as exc:
        raise ApiError("SLUG_TAKEN", "Another course already uses this address.", status_code=409) from exc
    if c.status == "published" and "teacher_member_id" in changes:
        await profiles.ensure_for_member(session, changes["teacher_member_id"])
    await _audit(session, actor, "course.update", "class", c.id, {"changes": changes})
    return await get_course(session, actor, c.id)


async def delete_course(session: AsyncSession, actor: Actor, course_id: UUID) -> None:
    c = await _load(session, actor, course_id, for_update=True)
    if c.status != "draft" or c.first_published_at is not None:
        raise ApiError("CLASS_NOT_DRAFT", "Only a course that was never published can be deleted. Unpublish it instead.",
                       status_code=409)
    await _delete_or_conflict(session, lambda: _delete(session, c.id))
    await _audit(session, actor, "course.delete", "class", c.id, {"title": c.title})


async def _delete(session: AsyncSession, course_id: UUID) -> None:
    await session.execute(text("""DELETE FROM lesson_resources WHERE lesson_id IN
                                  (SELECT id FROM lessons WHERE class_id = :id)"""), {"id": course_id})
    await session.execute(text("DELETE FROM lessons WHERE class_id = :id"), {"id": course_id})
    await session.execute(text("DELETE FROM classes WHERE id = :id"), {"id": course_id})


async def submit(session: AsyncSession, actor: Actor, course_id: UUID) -> CourseDetail:
    """First publish: to EduZone's review queue. Later (after an unpublish): straight back to published."""
    c = await _load(session, actor, course_id, for_update=True)
    if c.status not in ("draft", "archived"):
        raise ApiError("STATUS_INVALID", f"A {c.status.replace('_', ' ')} course can't be submitted.", status_code=409)
    detail = await detail_of(session, c)
    if not detail.ready_to_submit:
        missing = [x.key for x in detail.checks if not x.ok]
        raise ApiError("COURSE_NOT_READY", f"Finish these first: {', '.join(missing)}.", status_code=409)
    await refresh_stats(session, c.id)
    if c.first_published_at is None:
        await session.execute(text("""
            UPDATE classes SET status = 'in_review', submitted_at = now(), review_note = NULL, updated_at = now()
            WHERE id = :id
        """), {"id": c.id})
        await _audit(session, actor, "course.submit", "class", c.id)
    else:
        await session.execute(text("UPDATE classes SET status = 'published', updated_at = now() WHERE id = :id"),
                              {"id": c.id})
        await profiles.ensure_for_member(session, c.teacher_member_id)
        await _audit(session, actor, "course.publish", "class", c.id)
    return await get_course(session, actor, c.id)


async def withdraw(session: AsyncSession, actor: Actor, course_id: UUID) -> CourseDetail:
    c = await _load(session, actor, course_id, for_update=True)
    if c.status != "in_review":
        raise ApiError("STATUS_INVALID", "Only a course in review can be withdrawn.", status_code=409)
    await session.execute(text("UPDATE classes SET status = 'draft', updated_at = now() WHERE id = :id"), {"id": c.id})
    await _audit(session, actor, "course.withdraw", "class", c.id)
    return await get_course(session, actor, c.id)


async def unpublish(session: AsyncSession, actor: Actor, course_id: UUID) -> CourseDetail:
    """Stops new sales; buyers keep access (their grants never depend on the course's status)."""
    c = await _load(session, actor, course_id, for_update=True)
    if c.status != "published":
        raise ApiError("STATUS_INVALID", "Only a published course can be unpublished.", status_code=409)
    await session.execute(text("UPDATE classes SET status = 'archived', updated_at = now() WHERE id = :id"),
                          {"id": c.id})
    await _audit(session, actor, "course.unpublish", "class", c.id)
    return await get_course(session, actor, c.id)


# --- sections -------------------------------------------------------------------------------

async def _load_section(session: AsyncSession, actor: Actor, section_id: UUID) -> tuple[Any, Any]:
    s = (await session.execute(text("SELECT id, class_id, title, sort_order FROM course_sections WHERE id = :id FOR UPDATE"),
                               {"id": section_id})).one_or_none()
    if s is None:
        raise ApiError("NOT_FOUND", "Section not found.", status_code=404)
    try:
        c = await _load(session, actor, s.class_id, for_update=True)
    except ApiError:
        raise ApiError("NOT_FOUND", "Section not found.", status_code=404) from None
    return s, c


async def create_section(session: AsyncSession, actor: Actor, course_id: UUID, body: SectionCreate) -> CourseDetail:
    c = await _load(session, actor, course_id, for_update=True)
    _editable(c)
    order = body.sort_order
    if order is None:
        order = (await session.execute(text(
            "SELECT COALESCE(max(sort_order), -1) + 1 FROM course_sections WHERE class_id = :c"), {"c": c.id})).scalar_one()
    section_id = (await session.execute(text("""
        INSERT INTO course_sections (class_id, title, sort_order) VALUES (:c, :t, :o) RETURNING id
    """), {"c": c.id, "t": body.title.strip(), "o": order})).scalar_one()
    await _audit(session, actor, "course_section.create", "course_section", section_id, {"class_id": c.id})
    return await get_course(session, actor, c.id)


async def update_section(session: AsyncSession, actor: Actor, section_id: UUID, body: SectionUpdate) -> CourseDetail:
    s, c = await _load_section(session, actor, section_id)
    _editable(c)
    changes = {k: v for k, v in body.changes().items() if getattr(s, k) != v}
    if changes:
        sets = ", ".join(f"{k} = :{k}" for k in changes)
        await session.execute(text(f"UPDATE course_sections SET {sets}, updated_at = now() WHERE id = :id"),
                              {**changes, "id": s.id})
        await _audit(session, actor, "course_section.update", "course_section", s.id, {"changes": changes})
    return await get_course(session, actor, c.id)


async def delete_section(session: AsyncSession, actor: Actor, section_id: UUID) -> CourseDetail:
    s, c = await _load_section(session, actor, section_id)
    _editable(c)
    if (await session.execute(text("SELECT EXISTS (SELECT 1 FROM lessons WHERE section_id = :s)"), {"s": s.id})).scalar():
        raise ApiError("SECTION_NOT_EMPTY", "Move or delete this section's lectures first.", status_code=409)
    await session.execute(text("DELETE FROM course_sections WHERE id = :id"), {"id": s.id})
    await _audit(session, actor, "course_section.delete", "course_section", s.id, {"class_id": c.id})
    return await get_course(session, actor, c.id)


# --- lectures -------------------------------------------------------------------------------

async def _load_lecture(session: AsyncSession, actor: Actor, lecture_id: UUID) -> tuple[Any, Any]:
    lec = (await session.execute(text("""
        SELECT id, class_id, section_id, title, description, lesson_type, article_body, sort_order,
               is_free_preview, is_published
        FROM lessons WHERE id = :id AND section_id IS NOT NULL FOR UPDATE
    """), {"id": lecture_id})).one_or_none()
    if lec is None:
        raise ApiError("NOT_FOUND", "Lecture not found.", status_code=404)
    try:
        c = await _load(session, actor, lec.class_id, for_update=True)
    except ApiError:
        raise ApiError("NOT_FOUND", "Lecture not found.", status_code=404) from None
    return lec, c


def _check_article(lesson_type: str, body: str | None) -> None:
    if lesson_type == "article" and not (body or "").strip():
        raise ApiError("ARTICLE_REQUIRED", "An article lecture needs its text.", status_code=422)


async def _has_video(session: AsyncSession, lecture_id: UUID) -> bool:
    return (await session.execute(text("""
        SELECT EXISTS (SELECT 1 FROM lesson_resources r JOIN media_assets a ON a.id = r.media_asset_id
                       WHERE r.lesson_id = :l AND a.kind = 'video')
    """), {"l": lecture_id})).scalar_one()


async def create_lecture(session: AsyncSession, actor: Actor, section_id: UUID, body: LectureCreate) -> CourseDetail:
    s, c = await _load_section(session, actor, section_id)
    _editable(c)
    _check_article(body.lesson_type, body.article_body)
    order = body.sort_order
    if order is None:
        order = (await session.execute(text(
            "SELECT COALESCE(max(sort_order), -1) + 1 FROM lessons WHERE section_id = :s"), {"s": s.id})).scalar_one()
    lecture_id = (await session.execute(text("""
        INSERT INTO lessons (tenant_id, class_id, section_id, title, description, lesson_type, article_body, sort_order,
                             is_free_preview, is_published)
        VALUES (current_tenant_id(), :c, :s, :title, :descr, :type, :body, :o, :preview, :pub)
        RETURNING id
    """), {"c": c.id, "s": s.id, "title": body.title.strip(), "descr": body.description, "type": body.lesson_type,
           "body": body.article_body if body.lesson_type == "article" else None, "o": order,
           "preview": body.is_free_preview, "pub": body.is_published})).scalar_one()
    await refresh_stats(session, c.id)
    await _audit(session, actor, "lecture.create", "lesson", lecture_id,
                 {"class_id": c.id, "title": body.title, "lesson_type": body.lesson_type})
    return await get_course(session, actor, c.id)


async def update_lecture(session: AsyncSession, actor: Actor, lecture_id: UUID, body: LectureUpdate) -> CourseDetail:
    lec, c = await _load_lecture(session, actor, lecture_id)
    _editable(c)
    changes = {k: v for k, v in body.changes().items() if getattr(lec, k) != v}
    if not changes:
        return await get_course(session, actor, c.id)
    if "section_id" in changes:
        target = (await session.execute(text("SELECT class_id FROM course_sections WHERE id = :id"),
                                        {"id": changes["section_id"]})).scalar_one_or_none()
        if target != c.id:
            raise ApiError("SECTION_INVALID", "That section belongs to another course.", status_code=422)
    lesson_type = changes.get("lesson_type", lec.lesson_type)
    if "lesson_type" in changes:
        if lesson_type != "recorded" and await _has_video(session, lec.id):
            raise ApiError("MEDIA_KIND_INVALID", "Remove the video first: only video lectures have videos.", status_code=409)
        if lesson_type != "article":
            changes["article_body"] = None
    _check_article(lesson_type, changes.get("article_body", lec.article_body))
    sets = ", ".join(f"{k} = :{k}" for k in changes)
    await session.execute(text(f"UPDATE lessons SET {sets}, updated_at = now() WHERE id = :id"), {**changes, "id": lec.id})
    await refresh_stats(session, c.id)
    logged = {k: ("<changed>" if k == "article_body" else v) for k, v in changes.items()}
    await _audit(session, actor, "lecture.update", "lesson", lec.id, {"changes": logged})
    return await get_course(session, actor, c.id)


async def delete_lecture(session: AsyncSession, actor: Actor, lecture_id: UUID) -> CourseDetail:
    lec, c = await _load_lecture(session, actor, lecture_id)
    _editable(c)
    if c.first_published_at is not None and lec.is_published:
        # Buyers may be part-way through it; hiding keeps their progress meaningful.
        raise ApiError("LECTURE_PUBLISHED", "Unpublish this lecture instead of deleting it: students may have it.",
                       status_code=409)
    await _delete_or_conflict(session, lambda: _delete_lesson(session, lec.id))
    await refresh_stats(session, c.id)
    await _audit(session, actor, "lecture.delete", "lesson", lec.id, {"class_id": c.id, "title": lec.title})
    return await get_course(session, actor, c.id)


async def _delete_lesson(session: AsyncSession, lesson_id: UUID) -> None:
    await session.execute(text("DELETE FROM lesson_resources WHERE lesson_id = :l"), {"l": lesson_id})
    await session.execute(text("DELETE FROM lessons WHERE id = :l"), {"l": lesson_id})


async def categories(session: AsyncSession) -> list[dict[str, Any]]:
    rows = (await session.execute(text("""
        SELECT id, parent_id, slug, name_en, name_si, name_ta, sort_order, is_active FROM course_categories
        WHERE is_active ORDER BY parent_id NULLS FIRST, sort_order, name_en
    """))).all()
    return [dict(r._mapping) for r in rows]
