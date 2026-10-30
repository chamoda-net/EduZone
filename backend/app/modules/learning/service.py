"""Student side: browse published classes, join, see which months are unlocked, ask for
past months, open lessons and their files. All access decisions come from access.py."""

from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.pagination import decode_cursor, encode_cursor
from app.modules.auth.dependencies import AuthContext, ensure_student_member
from app.modules.learning import access
from app.modules.learning import repository as repo
from app.modules.learning.schemas import (
    LateRequestOut,
    MyClass,
    OpenResourceOut,
    PublicClass,
    PublicClassDetail,
    PublicClassPage,
    PublicLesson,
    PublicMonth,
    StudentClassView,
    StudentLesson,
    StudentLessonDetail,
    StudentMonth,
    StudentResource,
    Watermark,
)
from app.modules.media import repository as media_repo
from app.modules.media.service import signed_url


def _not_found(what: str = "Class") -> ApiError:
    return ApiError("NOT_FOUND", f"{what} not found.", status_code=404)


def _public_class(row: Any) -> PublicClass:
    return PublicClass.model_validate({k: getattr(row, k) for k in PublicClass.model_fields if k != "org"})


def _month(row: Any, currency: str) -> PublicMonth:
    return PublicMonth(id=row.id, month_start=row.month_start, fee_cents=row.fee_cents, currency=currency,
                       status=row.status)


def _lesson(row: Any) -> PublicLesson:
    return PublicLesson.model_validate({k: getattr(row, k) for k in PublicLesson.model_fields})


# --- public catalogue -----------------------------------------------------------------

async def list_published(session: AsyncSession, *, exam: str | None, cursor: str | None,
                         limit: int) -> PublicClassPage:
    rows = await repo.list_published(session, exam=exam, after=decode_cursor(cursor) if cursor else None,
                                     limit=limit + 1)
    page = rows[:limit]
    return PublicClassPage(
        items=[_public_class(r) for r in page],
        next_cursor=encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
    )


async def public_class(session: AsyncSession, slug: str) -> PublicClassDetail:
    c = await repo.class_by_slug(session, slug, published_only=True)
    if c is None:
        raise _not_found()
    months = await repo.class_months(session, c.id)
    lessons = await access.class_lessons_for_student(session, None, c.id)
    return PublicClassDetail(klass=_public_class(c), months=[_month(m, c.currency) for m in months],
                             lessons=[_lesson(lesson) for lesson in lessons])


# --- the signed-in student ------------------------------------------------------------

def _month_access(month: Any, granted: bool, allow_late: bool, request_status: str | None) -> str:
    if granted:
        return "granted"
    if month.status == "open":
        return "buy"
    if month.status == "upcoming":
        return "upcoming"
    if not allow_late:
        return "unavailable"
    return {"pending": "pending", "approved": "approved", "rejected": "rejected"}.get(request_status or "", "request")


async def class_view(session: AsyncSession, auth: AuthContext, slug: str) -> StudentClassView:
    c = await repo.class_by_slug(session, slug, published_only=False)
    if c is None:
        raise _not_found()
    grants = await repo.month_grants(session, auth.member_id, c.id)
    enrollment = await repo.enrollment(session, auth.member_id, c.id)
    # An archived class stays visible only to students who still have access to something in it.
    if c.status == "archived" and not grants:
        raise _not_found()
    requests = await repo.late_requests(session, auth.member_id, c.id)
    months = await repo.class_months(session, c.id)
    lessons = await access.class_lessons_for_student(session, auth.member_id, c.id)
    return StudentClassView(
        klass=_public_class(c),
        enrolled=enrollment is not None and enrollment.status == "active",
        has_class_access=None in grants,
        months=[
            StudentMonth(**_month(m, c.currency).model_dump(),
                         access=_month_access(m, m.id in grants, c.allow_late_months, requests.get(m.id)))
            for m in months
        ],
        lessons=[StudentLesson(**_lesson(lesson).model_dump(), unlocked=lesson.unlocked) for lesson in lessons],
    )


async def enroll(session: AsyncSession, auth: AuthContext, slug: str) -> StudentClassView:
    c = await repo.class_by_slug(session, slug, published_only=True)
    if c is None:
        raise _not_found()
    auth = await ensure_student_member(session, auth)  # joining makes them a member here
    await repo.upsert_enrollment(session, auth.member_id, c.id)
    # Free classes: joining is all it takes.
    if c.pricing_model == "free" and await access.active_grant_for(session, auth.member_id, c.id, None) is None:
        await repo.insert_grant(session, member_id=auth.member_id, class_id=c.id, month_id=None,
                                source="free", granted_by=None)
    return await class_view(session, auth, slug)


async def leave(session: AsyncSession, auth: AuthContext, slug: str) -> None:
    c = await repo.class_by_slug(session, slug, published_only=False)
    if c is None:
        raise _not_found()
    await repo.leave(session, auth.member_id, c.id)  # access already paid for is kept


async def my_classes(session: AsyncSession, auth: AuthContext) -> list[MyClass]:
    return [MyClass(klass=_public_class(r), enrolled_at=r.enrolled_at, unlocked_months=r.unlocked_months)
            for r in await repo.my_classes(session, auth.member_id)]


async def request_late_month(session: AsyncSession, auth: AuthContext, month_id: UUID,
                             note: str | None) -> LateRequestOut:
    m = await repo.month_with_class(session, month_id)
    if m is None or m.class_status != "published":
        raise _not_found("Month")
    enrollment = await repo.enrollment(session, auth.member_id, m.class_id)
    if enrollment is None or enrollment.status != "active":
        raise ApiError("NOT_ENROLLED", "Join the class first.", status_code=409)
    if not m.allow_late_months:
        raise ApiError("LATE_MONTHS_NOT_ALLOWED", "This class doesn't accept requests for past months.", 409)
    if m.status != "closed":
        raise ApiError("MONTH_NOT_CLOSED", "This month is not closed; you can pay for it directly.", 409)
    if await access.active_grant_for(session, auth.member_id, m.class_id, m.id) is not None:
        raise ApiError("ALREADY_HAS_ACCESS", "You already have access to this month.", 409)
    existing = await repo.late_request(session, auth.member_id, m.id)
    if existing is not None:
        code = "REQUEST_REJECTED" if existing.status == "rejected" else "REQUEST_EXISTS"
        raise ApiError(code, "You have already asked for this month.", 409)
    r = await repo.insert_late_request(session, auth.member_id, m.id, note.strip() if note else None)
    return LateRequestOut.model_validate(dict(r._mapping))


async def lesson_detail(session: AsyncSession, auth: AuthContext, lesson_id: UUID) -> StudentLessonDetail:
    lesson = await access.lesson_for_student(session, auth.member_id, lesson_id)
    if lesson is None:
        raise _not_found("Lesson")
    resources = await repo.lesson_resources(session, auth.member_id, lesson.id) if lesson.unlocked else []
    return StudentLessonDetail(
        **_lesson(lesson).model_dump(),
        unlocked=lesson.unlocked,
        class_id=lesson.class_id,
        class_slug=lesson.class_slug,
        class_title=lesson.class_title,
        description=lesson.description if lesson.unlocked else None,
        # Zoom links are hidden until the access check passes (CLAUDE.md section 10).
        zoom_join_url=lesson.zoom_join_url if lesson.unlocked else None,
        resources=[
            StudentResource(id=r.id, title=r.title, kind=r.kind, duration_seconds=r.duration_seconds,
                            is_downloadable=r.is_downloadable, ready=r.ready, views_used=r.views_used,
                            views_allowed=lesson.max_video_views if r.kind == "video" else None)
            for r in resources
        ],
    )


async def open_resource(session: AsyncSession, auth: AuthContext, resource_id: UUID) -> OpenResourceOut:
    """Signed URL for a lesson file, after the access check. Starting a video counts a view
    (blocked at the class's limit)."""
    r = await repo.resource(session, resource_id)
    if r is None:
        raise _not_found("File")
    lesson = await access.lesson_for_student(session, auth.member_id, r.lesson_id)
    if lesson is None:
        raise _not_found("File")
    if not lesson.unlocked:
        raise ApiError("ACCESS_DENIED", "You don't have access to this lesson yet.", status_code=403)
    asset = await media_repo.get_asset(session, r.media_asset_id)
    if asset is None:
        raise _not_found("File")
    if asset.kind == "video" and asset.status != "ready":
        raise ApiError("MEDIA_NOT_READY", "This video is still processing.", 409)
    auth = await ensure_student_member(session, auth)  # free previews: views are counted per member

    views = None
    if asset.kind == "video":
        views = await repo.count_view(session, auth.member_id, r.id, lesson.max_video_views)
        if views is None:
            raise ApiError("VIEW_LIMIT_REACHED", "You have used all the views allowed for this video.", 403)
    url = await signed_url(session, asset)
    who = await repo.member_identity(session, auth.member_id)
    return OpenResourceOut(
        kind=asset.kind, url=url.url, expires_at=url.expires_at,
        watermark=Watermark(name=who.full_name, phone=who.phone),
        views_used=views, views_allowed=lesson.max_video_views if asset.kind == "video" else None,
    )
