"""Courses for students (docs/COURSES.md, step C3): the course player's data, free enrolment, lecture completion
and progress, and "My courses" across tenants.

Buying a course is the ordinary cart and checkout (a course is a one-time class): fulfilment gives a class-level
access grant with no expiry, which is lifetime access. Every request about one course runs in that course's tenant
(`learn.service.in_tenant_of`), so THE access rule in learning/access.py decides what opens, as for classes.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.core.tenancy import tenant_transaction
from app.modules.auth.dependencies import AuthContext, UserContext, ensure_student_member
from app.modules.courses.schemas import (
    CompletionOut,
    CourseProgress,
    LearnCourse,
    LearnLecture,
    LearnSection,
    LectureDetail,
    MyCourse,
)
from app.modules.learning import access
from app.modules.learning import repository as learning_repo
from app.modules.learning.schemas import StudentResource

_COURSE = """
    SELECT c.id, c.slug, c.title, c.subtitle, c.cover_image_url, c.status, c.pricing_model, c.one_time_price_cents,
           c.welcome_message, c.completion_message, t.currency, t.name AS org_name,
           COALESCE(NULLIF(tm.display_name, ''), u.full_name) AS teacher_name, tp.slug AS teacher_slug
    FROM classes c
    JOIN tenants t ON t.id = c.tenant_id
    JOIN tenant_members tm ON tm.id = c.teacher_member_id
    JOIN users u ON u.id = tm.user_id
    LEFT JOIN teacher_profiles tp ON tp.user_id = tm.user_id
    WHERE c.id = :id AND c.kind = 'course'
"""

# Published lectures of a course in curriculum order, with ready video length and this student's completion.
_LECTURES = """
    SELECT l.id, l.section_id, l.title, l.lesson_type, l.is_free_preview,
           s.title AS section_title,
           COALESCE((SELECT sum(a.duration_seconds) FROM lesson_resources r
                     JOIN media_assets a ON a.id = r.media_asset_id AND a.kind = 'video' AND a.status = 'ready'
                     WHERE r.lesson_id = l.id), 0)::int AS video_seconds,
           EXISTS (SELECT 1 FROM lesson_completions lc
                   WHERE lc.lesson_id = l.id AND lc.student_member_id = CAST(:m AS uuid)) AS completed
    FROM lessons l JOIN course_sections s ON s.id = l.section_id
    WHERE l.class_id = :c AND l.is_published
    ORDER BY s.sort_order, s.created_at, l.sort_order, l.created_at
"""


def _not_found() -> ApiError:
    return ApiError("NOT_FOUND", "Course not found.", status_code=404)


def progress_of(lectures: list[Any]) -> CourseProgress:
    total = len(lectures)
    done = sum(1 for lec in lectures if lec.completed)
    return CourseProgress(completed=done, total=total, percent=(done * 100 // total) if total else 0)


async def _has_access(session: AsyncSession, auth: AuthContext, course_id: UUID) -> bool:
    if auth.member_id is None:
        return False
    return await access.active_grant_for(session, auth.member_id, course_id, None) is not None


async def _load(session: AsyncSession, auth: AuthContext, course_id: UUID) -> tuple[Any, bool]:
    """The course and whether this student has access. Published courses for anyone; an unpublished (archived)
    course stays open to the students who already have it."""
    c = (await session.execute(text(_COURSE), {"id": course_id})).one_or_none()
    if c is None:
        raise _not_found()
    has = await _has_access(session, auth, course_id)
    if c.status != "published" and not (c.status == "archived" and has):
        raise _not_found()
    return c, has


async def _lectures(session: AsyncSession, auth: AuthContext, course_id: UUID) -> list[Any]:
    return list((await session.execute(text(_LECTURES), {"c": course_id, "m": auth.member_id})).all())


async def course_view(session: AsyncSession, auth: AuthContext, course_id: UUID) -> LearnCourse:
    c, has = await _load(session, auth, course_id)
    lectures = await _lectures(session, auth, course_id)
    progress = progress_of(lectures)
    sections: list[LearnSection] = []
    for lec in lectures:
        if not sections or sections[-1].id != lec.section_id:
            sections.append(LearnSection(id=lec.section_id, title=lec.section_title, lectures=[], completed=0, total=0))
        s = sections[-1]
        s.lectures.append(LearnLecture(id=lec.id, title=lec.title, lesson_type=lec.lesson_type,
                                       video_seconds=lec.video_seconds, is_free_preview=lec.is_free_preview,
                                       unlocked=has or lec.is_free_preview, completed=lec.completed))
        s.total += 1
        s.completed += int(lec.completed)
    upcoming = next((lec.id for lec in lectures if not lec.completed and (has or lec.is_free_preview)), None)
    return LearnCourse(
        id=c.id, slug=c.slug, title=c.title, subtitle=c.subtitle, cover_image_url=c.cover_image_url, status=c.status,
        path=f"/course/{c.slug}", teacher_name=c.teacher_name, teacher_slug=c.teacher_slug, org_name=c.org_name,
        pricing_model=c.pricing_model, one_time_price_cents=c.one_time_price_cents, currency=c.currency,
        has_access=has, welcome_message=c.welcome_message if has else None,
        completion_message=c.completion_message if has and progress.total and progress.percent == 100 else None,
        progress=progress, sections=sections,
        next_lecture_id=upcoming or (lectures[0].id if lectures and has else None),
    )


async def enroll(session: AsyncSession, auth: AuthContext, course_id: UUID) -> LearnCourse:
    """A free course: enrolling gives lifetime access (a `free` grant). Paid courses go through the cart."""
    c, has = await _load(session, auth, course_id)
    if c.status != "published":
        raise _not_found()
    if c.pricing_model != "free":
        raise ApiError("NOT_FREE", "This course is paid: add it to your cart.", status_code=409)
    auth = await ensure_student_member(session, auth)
    assert auth.member_id is not None
    if not has:
        await learning_repo.upsert_enrollment(session, auth.member_id, course_id)
        await learning_repo.insert_grant(session, member_id=auth.member_id, class_id=course_id, month_id=None,
                                         source="free", granted_by=None)
    return await course_view(session, auth, course_id)


async def _lecture(session: AsyncSession, auth: AuthContext, lecture_id: UUID) -> Any:
    lesson = await access.lesson_for_student(session, auth.member_id, lecture_id)
    if lesson is None or lesson.section_id is None:
        raise ApiError("NOT_FOUND", "Lecture not found.", status_code=404)
    return lesson


async def lecture_detail(session: AsyncSession, auth: AuthContext, lecture_id: UUID) -> LectureDetail:
    lesson = await _lecture(session, auth, lecture_id)
    await _load(session, auth, lesson.class_id)
    lectures = await _lectures(session, auth, lesson.class_id)
    index = next(i for i, lec in enumerate(lectures) if lec.id == lesson.id)
    resources = await learning_repo.lesson_resources(session, auth.member_id, lesson.id) if lesson.unlocked else []
    return LectureDetail(
        id=lesson.id, course_id=lesson.class_id, section_title=lectures[index].section_title, title=lesson.title,
        lesson_type=lesson.lesson_type,
        description=lesson.description if lesson.unlocked else None,
        article_body=lesson.article_body if lesson.unlocked else None,
        unlocked=lesson.unlocked, completed=lectures[index].completed,
        resources=[StudentResource(id=r.id, title=r.title, kind=r.kind, duration_seconds=r.duration_seconds,
                                   is_downloadable=r.is_downloadable, ready=r.ready, views_used=r.views_used,
                                   views_allowed=lesson.max_video_views if r.kind == "video" else None,
                                   position_seconds=r.position_seconds, completed=r.completed)
                   for r in resources],
        prev_id=lectures[index - 1].id if index > 0 else None,
        next_id=lectures[index + 1].id if index + 1 < len(lectures) else None,
    )


async def set_completed(session: AsyncSession, auth: AuthContext, lecture_id: UUID, done: bool) -> CompletionOut:
    """Mark a lecture complete (articles and PDFs; videos complete themselves at 90%) or un-mark it. Only
    students who have the course count progress."""
    lesson = await _lecture(session, auth, lecture_id)
    if not await _has_access(session, auth, lesson.class_id):
        raise ApiError("ACCESS_DENIED", "Enrol in the course to track your progress.", status_code=403)
    assert auth.member_id is not None
    if done:
        await learning_repo.complete_lecture(session, auth.member_id, lesson.id, "manual")
    else:
        await session.execute(text("DELETE FROM lesson_completions WHERE student_member_id = :m AND lesson_id = :l"),
                              {"m": auth.member_id, "l": lesson.id})
    return CompletionOut(lecture_id=lesson.id, completed=done,
                         progress=progress_of(await _lectures(session, auth, lesson.class_id)))


async def my_courses(user: UserContext, memberships: list[Any]) -> list[MyCourse]:
    """Every course this user has access to, in each tenant where they are a member."""
    out: list[MyCourse] = []
    for m in memberships:
        async with tenant_transaction(m.tenant_id) as session:
            rows = (await session.execute(text(f"""
                SELECT c.id, c.slug, c.title, c.cover_image_url,
                       COALESCE(NULLIF(tm.display_name, ''), u.full_name) AS teacher_name,
                       min(g.granted_at) AS started_at,
                       (SELECT max(lc.completed_at) FROM lesson_completions lc JOIN lessons l ON l.id = lc.lesson_id
                        WHERE l.class_id = c.id AND lc.student_member_id = :m) AS last_activity_at
                FROM access_grants g
                JOIN classes c ON c.id = g.class_id AND c.kind = 'course' AND c.status IN ('published', 'archived')
                JOIN tenant_members tm ON tm.id = c.teacher_member_id
                JOIN users u ON u.id = tm.user_id
                WHERE g.student_member_id = :m AND g.class_month_id IS NULL AND {access.ACTIVE_GRANT}
                GROUP BY c.id, tm.display_name, u.full_name
            """), {"m": m.member_id})).all()
            auth = AuthContext(user.user_id, m.member_id, "student", user.session_id)
            for r in rows:
                lectures = await _lectures(session, auth, r.id)
                upcoming = next((lec.id for lec in lectures if not lec.completed), lectures[0].id if lectures else None)
                out.append(MyCourse(id=r.id, slug=r.slug, title=r.title, cover_image_url=r.cover_image_url,
                                    teacher_name=r.teacher_name, org_name=m.name, progress=progress_of(lectures),
                                    next_lecture_id=upcoming, started_at=r.started_at,
                                    last_activity_at=r.last_activity_at))
    return sorted(out, key=lambda c: c.last_activity_at or c.started_at, reverse=True)
