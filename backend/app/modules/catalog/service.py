"""Catalogue rules for the organization console: classes -> months -> lessons.

Permissions: owners and admins manage every class; a teacher manages only classes they
teach. A class the caller may not manage is reported as not found, so its existence
doesn't leak.
"""

import re
import secrets
import unicodedata
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.errors import ApiError
from app.core.pagination import decode_cursor, encode_cursor
from app.modules.auth.dependencies import STAFF_ROLES, Actor
from app.modules.catalog import repository as repo
from app.modules.catalog.models import ClassModel, ClassMonth, Lesson
from app.modules.catalog.schemas import (
    ClassCreate,
    ClassOut,
    ClassPage,
    ClassUpdate,
    LessonCreate,
    LessonOut,
    LessonUpdate,
    MonthCreate,
    MonthOut,
    MonthUpdate,
)
from app.modules.market import profiles

# Allowed class status changes. A published class never goes back to draft:
# students may already have paid for it.
_STATUS_FLOW = {
    "draft": {"published", "archived"},
    "published": {"archived"},
    "archived": {"published"},
}

_STATUS_ACTIONS = {"published": "class.publish", "archived": "class.archive"}

_FK_VIOLATION = "23503"


def _not_found(what: str) -> ApiError:
    return ApiError("NOT_FOUND", f"{what} not found.", status_code=404)


def _sqlstate(exc: IntegrityError) -> str | None:
    return getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)


async def _audit(session: AsyncSession, actor: Actor, action: str, entity_type: str,
                 entity_id: UUID, details: dict[str, Any] | None = None) -> None:
    await write_audit(session, actor_user_id=actor.auth.user_id, action=action, entity_type=entity_type,
                      entity_id=entity_id, details=details, ip=actor.ip)


# --- classes --------------------------------------------------------------------------

def _class_out(c: ClassModel, currency: str) -> ClassOut:
    return ClassOut.model_validate({**{k: getattr(c, k) for k in ClassOut.model_fields if k != "currency"},
                                    "currency": currency})


async def _load_class(session: AsyncSession, actor: Actor, class_id: UUID, *,
                      for_update: bool = False) -> ClassModel:
    c = await repo.get_class(session, class_id, for_update=for_update)
    if c is None or not (actor.manages_all or c.teacher_member_id == actor.auth.member_id):
        raise _not_found("Class")
    return c


def _check_pricing(pricing_model: str, monthly_fee: int | None, one_time_price: int | None) -> None:
    if pricing_model == "monthly" and monthly_fee is None:
        raise ApiError("PRICING_INVALID", "A monthly class needs monthly_fee_cents.")
    if pricing_model == "one_time" and one_time_price is None:
        raise ApiError("PRICING_INVALID", "A one-time class needs one_time_price_cents.")


async def _check_teacher(session: AsyncSession, actor: Actor, member_id: UUID) -> None:
    if member_id != actor.auth.member_id and not actor.manages_all:
        raise ApiError("ACCESS_DENIED", "Only owners and admins can assign another teacher.", status_code=403)
    member = await repo.get_member(session, member_id)
    if member is None or member.status != "active" or member.role not in STAFF_ROLES:
        raise ApiError("TEACHER_INVALID", "The teacher must be an active staff member of this organization.")


def _slugify(title: str) -> str:
    ascii_title = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", ascii_title).strip("-")[:60].strip("-") or "class"


async def _unique_slug(session: AsyncSession, title: str) -> str:
    base = _slugify(title)
    slug = base
    while await repo.class_slug_taken(session, slug):
        slug = f"{base}-{secrets.token_hex(2)}"
    return slug


async def list_classes(session: AsyncSession, actor: Actor, *, status: str | None, cursor: str | None,
                       limit: int) -> ClassPage:
    rows = await repo.list_classes(
        session,
        teacher_member_id=None if actor.manages_all else actor.auth.member_id,
        status=status,
        after=decode_cursor(cursor) if cursor else None,
        limit=limit + 1,
    )
    currency = await repo.get_currency(session)
    page, more = rows[:limit], len(rows) > limit
    return ClassPage(
        items=[_class_out(c, currency) for c in page],
        next_cursor=encode_cursor(page[-1].created_at, page[-1].id) if more else None,
    )


async def _subject_name(session: AsyncSession, subject_id: UUID) -> str:
    name = (await session.execute(text("SELECT name FROM subjects WHERE id = :id AND is_active"),
                                  {"id": subject_id})).scalar_one_or_none()
    if name is None:
        raise ApiError("SUBJECT_INVALID", "Choose a subject from the list.", status_code=422)
    return str(name)


async def get_class(session: AsyncSession, actor: Actor, class_id: UUID) -> ClassOut:
    return _class_out(await _load_class(session, actor, class_id), await repo.get_currency(session))


async def create_class(session: AsyncSession, actor: Actor, body: ClassCreate) -> ClassOut:
    values = body.model_dump()
    values["teacher_member_id"] = body.teacher_member_id or actor.auth.member_id
    if body.subject_id is not None:
        values["subject"] = await _subject_name(session, body.subject_id)
    await _check_teacher(session, actor, values["teacher_member_id"])
    _check_pricing(body.pricing_model, body.monthly_fee_cents, body.one_time_price_cents)
    if body.slug is None:
        values["slug"] = await _unique_slug(session, body.title)
    elif await repo.class_slug_taken(session, body.slug):
        raise ApiError("SLUG_TAKEN", "Another class already uses this slug.", status_code=409)

    c = await repo.insert_class(session, values)
    await _audit(session, actor, "class.create", "class", c.id, {"title": c.title, "slug": c.slug})
    return _class_out(c, await repo.get_currency(session))


async def update_class(session: AsyncSession, actor: Actor, class_id: UUID, body: ClassUpdate) -> ClassOut:
    c = await _load_class(session, actor, class_id, for_update=True)
    changes = {k: v for k, v in body.changes().items() if getattr(c, k) != v}
    if not changes:
        return _class_out(c, await repo.get_currency(session))

    if "teacher_member_id" in changes:
        if not actor.manages_all:
            raise ApiError("ACCESS_DENIED", "Only owners and admins can reassign a class.", status_code=403)
        await _check_teacher(session, actor, changes["teacher_member_id"])
    if "status" in changes and changes["status"] not in _STATUS_FLOW[c.status]:
        raise ApiError("STATUS_INVALID", f"A {c.status} class cannot become {changes['status']}.", status_code=409)
    if changes.get("status") == "published" and await repo.tenant_status(session) != "active":
        # Draft mode: an organization waiting for EduZone's approval prepares classes but can't publish.
        raise ApiError("TENANT_NOT_APPROVED", "You can publish once EduZone approves your application.", status_code=409)
    if "pricing_model" in changes and (c.status != "draft" or await repo.class_has_content(session, c.id)):
        raise ApiError("PRICING_LOCKED",
                       "The pricing model can only change on a draft class with no months or lessons.",
                       status_code=409)
    if "slug" in changes and await repo.class_slug_taken(session, changes["slug"], exclude_id=c.id):
        raise ApiError("SLUG_TAKEN", "Another class already uses this slug.", status_code=409)

    if changes.get("subject_id") is not None:
        changes["subject"] = await _subject_name(session, changes["subject_id"])

    merged = {k: changes.get(k, getattr(c, k))
              for k in ("pricing_model", "monthly_fee_cents", "one_time_price_cents")}
    _check_pricing(merged["pricing_model"], merged["monthly_fee_cents"], merged["one_time_price_cents"])

    updated = await repo.update_class(session, c.id, changes)
    if updated.status == "published" and ({"status", "teacher_member_id"} & set(changes)):
        # Published classes appear on the marketplace under their teacher's public profile.
        await profiles.ensure_for_member(session, updated.teacher_member_id)
    action = _STATUS_ACTIONS[changes["status"]] if set(changes) == {"status"} else "class.update"
    await _audit(session, actor, action, "class", c.id, {"changes": changes})
    return _class_out(updated, await repo.get_currency(session))


async def delete_class(session: AsyncSession, actor: Actor, class_id: UUID) -> None:
    c = await _load_class(session, actor, class_id, for_update=True)
    if c.status != "draft":
        raise ApiError("CLASS_NOT_DRAFT", "Only draft classes can be deleted. Archive it instead.", status_code=409)
    await _delete_or_conflict(session, lambda: repo.delete_class(session, c.id))
    await _audit(session, actor, "class.delete", "class", c.id, {"title": c.title})


async def _delete_or_conflict(session: AsyncSession, op: Callable[[], Awaitable[None]]) -> None:
    # A savepoint keeps the request's transaction usable if the delete hits a foreign key.
    try:
        async with session.begin_nested():
            await op()
    except IntegrityError as exc:
        if _sqlstate(exc) == _FK_VIOLATION:
            raise ApiError("IN_USE", "This is already used by enrolments, payments or access grants.",
                           status_code=409) from exc
        raise


# --- months ---------------------------------------------------------------------------

def _month_out(m: ClassMonth, c: ClassModel, currency: str) -> MonthOut:
    effective = m.fee_cents if m.fee_cents is not None else c.monthly_fee_cents
    return MonthOut(id=m.id, class_id=m.class_id, month_start=m.month_start, fee_cents=m.fee_cents,
                    effective_fee_cents=effective or 0, currency=currency, status=m.status,
                    created_at=m.created_at)


async def _load_month(session: AsyncSession, actor: Actor, month_id: UUID) -> tuple[ClassMonth, ClassModel]:
    m = await repo.get_month(session, month_id, for_update=True)
    if m is None:
        raise _not_found("Month")
    try:
        c = await _load_class(session, actor, m.class_id)
    except ApiError:
        raise _not_found("Month") from None
    return m, c


async def list_months(session: AsyncSession, actor: Actor, class_id: UUID) -> list[MonthOut]:
    c = await _load_class(session, actor, class_id)
    currency = await repo.get_currency(session)
    return [_month_out(m, c, currency) for m in await repo.list_months(session, c.id)]


async def create_month(session: AsyncSession, actor: Actor, class_id: UUID, body: MonthCreate) -> MonthOut:
    c = await _load_class(session, actor, class_id, for_update=True)
    if c.pricing_model != "monthly":
        raise ApiError("NOT_MONTHLY", "Only monthly classes have months.")
    if await repo.month_exists(session, c.id, body.month_start):
        raise ApiError("MONTH_EXISTS", "This month already exists for the class.", status_code=409)
    m = await repo.insert_month(session, {"class_id": c.id, **body.model_dump()})
    await _audit(session, actor, "class_month.create", "class_month", m.id,
                 {"class_id": c.id, "month_start": m.month_start})
    return _month_out(m, c, await repo.get_currency(session))


async def update_month(session: AsyncSession, actor: Actor, month_id: UUID, body: MonthUpdate) -> MonthOut:
    m, c = await _load_month(session, actor, month_id)
    changes = {k: v for k, v in body.changes().items() if getattr(m, k) != v}
    if changes:
        m = await repo.update_month(session, m.id, changes)
        await _audit(session, actor, "class_month.update", "class_month", m.id, {"changes": changes})
    return _month_out(m, c, await repo.get_currency(session))


async def delete_month(session: AsyncSession, actor: Actor, month_id: UUID) -> None:
    m, _ = await _load_month(session, actor, month_id)
    if await repo.month_has_lessons(session, m.id):
        raise ApiError("MONTH_HAS_LESSONS", "Delete or move this month's lessons first.", status_code=409)
    await _delete_or_conflict(session, lambda: repo.delete_month(session, m.id))
    await _audit(session, actor, "class_month.delete", "class_month", m.id,
                 {"class_id": m.class_id, "month_start": m.month_start})


# --- lessons --------------------------------------------------------------------------

async def _check_lesson(session: AsyncSession, c: ClassModel, *, class_month_id: UUID | None,
                        lesson_type: str, scheduled_at: datetime | None, zoom_join_url: str | None) -> None:
    if c.pricing_model == "monthly":
        if class_month_id is None:
            raise ApiError("MONTH_REQUIRED", "Lessons in a monthly class belong to a month.")
        month = await repo.get_month(session, class_month_id)
        if month is None or month.class_id != c.id:
            raise ApiError("MONTH_INVALID", "That month does not belong to this class.")
    elif class_month_id is not None:
        raise ApiError("MONTH_INVALID", "Only lessons in monthly classes have a month.")
    if lesson_type == "live" and scheduled_at is None:
        raise ApiError("SCHEDULE_REQUIRED", "A live lesson needs scheduled_at.")
    if lesson_type != "live" and zoom_join_url is not None:
        raise ApiError("ZOOM_NOT_ALLOWED", "Only live lessons have a Zoom link.")


async def load_class(session: AsyncSession, actor: Actor, class_id: UUID, *, for_update: bool = False) -> ClassModel:
    """A class the actor may manage, else 404. Shared with other modules (students, grants)."""
    return await _load_class(session, actor, class_id, for_update=for_update)


async def load_lesson(session: AsyncSession, actor: Actor, lesson_id: UUID) -> tuple[Lesson, ClassModel]:
    """A lesson (locked for update) and its class, if the actor may manage it; else 404.
    Shared with the media module for lesson files."""
    return await _load_lesson(session, actor, lesson_id)


async def _load_lesson(session: AsyncSession, actor: Actor, lesson_id: UUID) -> tuple[Lesson, ClassModel]:
    lesson = await repo.get_lesson(session, lesson_id, for_update=True)
    if lesson is None:
        raise _not_found("Lesson")
    try:
        c = await _load_class(session, actor, lesson.class_id)
    except ApiError:
        raise _not_found("Lesson") from None
    return lesson, c


async def list_lessons(session: AsyncSession, actor: Actor, class_id: UUID,
                       month_id: UUID | None) -> list[LessonOut]:
    c = await _load_class(session, actor, class_id)
    return [LessonOut.model_validate(x) for x in await repo.list_lessons(session, c.id, month_id)]


async def create_lesson(session: AsyncSession, actor: Actor, class_id: UUID, body: LessonCreate) -> LessonOut:
    c = await _load_class(session, actor, class_id, for_update=True)
    await _check_lesson(session, c, class_month_id=body.class_month_id, lesson_type=body.lesson_type,
                        scheduled_at=body.scheduled_at, zoom_join_url=body.zoom_join_url)
    lesson = await repo.insert_lesson(session, {"class_id": c.id, **body.model_dump()})
    await _audit(session, actor, "lesson.create", "lesson", lesson.id,
                 {"class_id": c.id, "title": lesson.title, "lesson_type": lesson.lesson_type})
    return LessonOut.model_validate(lesson)


async def update_lesson(session: AsyncSession, actor: Actor, lesson_id: UUID, body: LessonUpdate) -> LessonOut:
    lesson, c = await _load_lesson(session, actor, lesson_id)
    changes = {k: v for k, v in body.changes().items() if getattr(lesson, k) != v}
    if not changes:
        return LessonOut.model_validate(lesson)
    merged = {k: changes.get(k, getattr(lesson, k))
              for k in ("class_month_id", "lesson_type", "scheduled_at", "zoom_join_url")}
    await _check_lesson(session, c, **merged)
    lesson = await repo.update_lesson(session, lesson.id, changes)
    await _audit(session, actor, "lesson.update", "lesson", lesson.id,
                 {"changes": {k: ("<changed>" if k == "zoom_join_url" else v) for k, v in changes.items()}})
    return LessonOut.model_validate(lesson)


async def delete_lesson(session: AsyncSession, actor: Actor, lesson_id: UUID) -> None:
    lesson, _ = await _load_lesson(session, actor, lesson_id)
    await _delete_or_conflict(session, lambda: repo.delete_lesson(session, lesson.id))
    await _audit(session, actor, "lesson.delete", "lesson", lesson.id,
                 {"class_id": lesson.class_id, "title": lesson.title})
