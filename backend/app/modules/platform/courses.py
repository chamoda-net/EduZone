"""Courses in the platform admin (docs/COURSES.md, step C1): course categories and the review queue.

EduZone staff review only the first publish of each course: approve (it goes live) or request changes (back to
draft with a note the instructor sees). Staff may also unpublish a live course at any time; buyers keep access.
Runs as eduzone_admin; tenant-scoped writes set app.tenant_id first so audit rows carry the tenant.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.courses import service as courses
from app.modules.courses.schemas import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    CourseDetail,
    ReviewDecision,
    ReviewRow,
    UnpublishIn,
)
from app.modules.market import profiles
from app.modules.platform.auth import PlatformActor
from app.modules.platform.service import _audit, _set_tenant

# --- categories ----------------------------------------------------------------------------

_CATEGORY = "SELECT id, parent_id, slug, name_en, name_si, name_ta, sort_order, is_active FROM course_categories"


async def list_categories(session: AsyncSession) -> list[CategoryOut]:
    rows = (await session.execute(text(_CATEGORY + " ORDER BY parent_id NULLS FIRST, sort_order, name_en"))).all()
    return [CategoryOut.model_validate(dict(r._mapping)) for r in rows]


async def _category(session: AsyncSession, category_id: int) -> CategoryOut:
    r = (await session.execute(text(_CATEGORY + " WHERE id = :id"), {"id": category_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Category not found.", status_code=404)
    return CategoryOut.model_validate(dict(r._mapping))


async def create_category(session: AsyncSession, actor: PlatformActor, body: CategoryCreate) -> CategoryOut:
    if body.parent_id is not None:
        parent = await _category(session, body.parent_id)
        if parent.parent_id is not None:
            raise ApiError("CATEGORY_DEPTH", "Categories have two levels: pick a top-level parent.", status_code=422)
    try:
        async with session.begin_nested():
            category_id = (await session.execute(text("""
                INSERT INTO course_categories (slug, name_en, name_si, name_ta, parent_id, sort_order)
                VALUES (:slug, :en, :si, :ta, :parent, :sort) RETURNING id
            """), {"slug": body.slug, "en": body.name_en.strip(), "si": body.name_si, "ta": body.name_ta,
                   "parent": body.parent_id, "sort": body.sort_order})).scalar_one()
    except IntegrityError as exc:
        raise ApiError("SLUG_TAKEN", "Another category already uses this address.", status_code=409) from exc
    await _audit_category(session, actor, "platform.course_category.create", category_id, {"slug": body.slug})
    return await _category(session, category_id)


async def update_category(session: AsyncSession, actor: PlatformActor, category_id: int,
                          body: CategoryUpdate) -> CategoryOut:
    current = await _category(session, category_id)
    changes = {k: v for k, v in body.changes().items() if getattr(current, k) != v}
    if changes:
        sets = ", ".join(f"{k} = :{k}" for k in changes)
        await session.execute(text(f"UPDATE course_categories SET {sets} WHERE id = :id"), {**changes, "id": category_id})
        await _audit_category(session, actor, "platform.course_category.update", category_id, {"changes": changes})
    return await _category(session, category_id)


async def _audit_category(session: AsyncSession, actor: PlatformActor, action: str, category_id: int,
                          details: dict[str, Any]) -> None:
    # Categories have smallint ids; the audit row's entity_id is a uuid, so the id goes in the details.
    await _audit(session, actor, action, "course_category", None, {"category_id": category_id, **details})


# --- review queue ----------------------------------------------------------------------------

async def list_reviews(session: AsyncSession, status: str) -> list[ReviewRow]:
    rows = (await session.execute(text("""
        SELECT c.id, c.tenant_id, t.name AS tenant_name, c.title,
               COALESCE(NULLIF(tm.display_name, ''), u.full_name) AS teacher_name, cc.name_en AS category_name,
               c.lecture_count, c.total_video_seconds, c.pricing_model, c.one_time_price_cents, t.currency,
               c.submitted_at
        FROM classes c
        JOIN tenants t ON t.id = c.tenant_id
        JOIN tenant_members tm ON tm.id = c.teacher_member_id
        JOIN users u ON u.id = tm.user_id
        LEFT JOIN course_categories cc ON cc.id = c.category_id
        WHERE c.kind = 'course' AND c.status = :st
        ORDER BY c.submitted_at NULLS LAST, c.updated_at DESC
    """), {"st": status})).all()
    return [ReviewRow.model_validate(dict(r._mapping)) for r in rows]


async def _load(session: AsyncSession, course_id: UUID, *, for_update: bool = False) -> Any:
    if for_update:
        await session.execute(text("SELECT 1 FROM classes WHERE id = :id FOR UPDATE"), {"id": course_id})
    r = (await session.execute(text(courses._ROW + " AND c.id = :id"), {"id": course_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Course not found.", status_code=404)
    await _set_tenant(session, r.tenant_id)
    return r


async def get_course(session: AsyncSession, course_id: UUID) -> CourseDetail:
    c = await _load(session, course_id)
    detail = await courses.detail_of(session, c)
    detail.tenant_name = (await session.execute(text("SELECT name FROM tenants WHERE id = :t"),
                                                {"t": c.tenant_id})).scalar_one()
    return detail


async def decide(session: AsyncSession, actor: PlatformActor, course_id: UUID, body: ReviewDecision) -> CourseDetail:
    c = await _load(session, course_id, for_update=True)
    if c.status != "in_review":
        raise ApiError("STATUS_INVALID", "Only a course in review can be decided.", status_code=409)
    note = (body.note or "").strip() or None
    if body.decision == "approve":
        detail = await courses.detail_of(session, c)
        if not detail.ready_to_submit:
            missing = [x.key for x in detail.checks if not x.ok]
            raise ApiError("COURSE_NOT_READY", f"It no longer passes: {', '.join(missing)}.", status_code=409)
        await courses.refresh_stats(session, c.id)
        await session.execute(text("""
            UPDATE classes SET status = 'published', first_published_at = now(), review_note = NULL, updated_at = now()
            WHERE id = :id
        """), {"id": c.id})
        await profiles.ensure_for_member(session, c.teacher_member_id)
    else:
        if note is None:
            raise ApiError("NOTE_REQUIRED", "Tell the instructor what to change.", status_code=422)
        await session.execute(text("""
            UPDATE classes SET status = 'draft', review_note = :note, updated_at = now() WHERE id = :id
        """), {"note": note, "id": c.id})
    await _audit(session, actor, f"platform.course.{body.decision}", "class", c.id, {"note": note, "title": c.title})
    return await get_course(session, c.id)


async def unpublish(session: AsyncSession, actor: PlatformActor, course_id: UUID, body: UnpublishIn) -> CourseDetail:
    c = await _load(session, course_id, for_update=True)
    if c.status != "published":
        raise ApiError("STATUS_INVALID", "Only a published course can be unpublished.", status_code=409)
    await session.execute(text("""
        UPDATE classes SET status = 'archived', review_note = :note, updated_at = now() WHERE id = :id
    """), {"note": body.note.strip(), "id": c.id})
    await _audit(session, actor, "platform.course.unpublish", "class", c.id, {"note": body.note, "title": c.title})
    return await get_course(session, c.id)
