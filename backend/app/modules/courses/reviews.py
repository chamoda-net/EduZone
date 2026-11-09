"""Course reviews (docs/COURSES.md section C.5, step C4).

- A student with access to a course writes one review (1-5 stars and a comment) and may edit or delete it.
- The instructor replies (one reply, editable). EduZone staff hide a review with a reason, or show it again.
- classes.rating_avg / rating_count come from visible reviews only and are recomputed in the same transaction as
  every change. The marketplace reads visible reviews through public_course_reviews (first name and initial only).
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AppSession
from app.core.errors import ApiError
from app.modules.auth.dependencies import Actor, AuthContext
from app.modules.courses import service as courses
from app.modules.courses.schemas import (
    HideIn,
    MyReview,
    PublicReview,
    PublicReviewPage,
    ReplyIn,
    ReviewIn,
    ReviewSummary,
    StaffReview,
)
from app.modules.learning import access
from app.modules.market.service import _decode_offset, _encode_offset

_REVIEWER = """CASE WHEN array_length(n.w, 1) > 1
                    THEN n.w[1] || ' ' || upper(left(n.w[array_length(n.w, 1)], 1)) || '.' ELSE n.w[1] END"""

_STAFF = f"""
    SELECT r.id, r.class_id AS course_id, c.title AS course_title, r.rating, r.comment, {_REVIEWER} AS reviewer,
           r.status, r.hidden_reason, r.instructor_reply, r.replied_at, r.created_at, t.name AS tenant_name
    FROM course_reviews r
    JOIN classes c ON c.id = r.class_id
    JOIN tenants t ON t.id = r.tenant_id
    JOIN tenant_members tm ON tm.id = r.student_member_id
    JOIN users u ON u.id = tm.user_id
    CROSS JOIN LATERAL (SELECT regexp_split_to_array(btrim(u.full_name), '[[:space:]]+') AS w) n
"""


def _staff(r: Any) -> StaffReview:
    return StaffReview.model_validate(dict(r._mapping))


async def recompute_rating(session: AsyncSession, course_id: UUID) -> None:
    await session.execute(text("""
        UPDATE classes c SET
            rating_avg = (SELECT round(avg(rating)::numeric, 2) FROM course_reviews
                          WHERE class_id = c.id AND status = 'visible'),
            rating_count = (SELECT count(*) FROM course_reviews WHERE class_id = c.id AND status = 'visible')
        WHERE c.id = :c
    """), {"c": course_id})


# --- the student --------------------------------------------------------------------------

async def _mine(session: AsyncSession, member_id: UUID | None, course_id: UUID) -> Any:
    if member_id is None:
        return None
    return (await session.execute(text("""
        SELECT id, rating, comment, status, instructor_reply, replied_at, created_at, updated_at
        FROM course_reviews WHERE class_id = :c AND student_member_id = :m
    """), {"c": course_id, "m": member_id})).one_or_none()


async def my_review(session: AsyncSession, auth: AuthContext, course_id: UUID) -> MyReview | None:
    r = await _mine(session, auth.member_id, course_id)
    return MyReview.model_validate(dict(r._mapping)) if r else None


async def _require_access(session: AsyncSession, auth: AuthContext, course_id: UUID) -> UUID:
    kind = (await session.execute(text("SELECT kind FROM classes WHERE id = :c"), {"c": course_id})).scalar_one_or_none()
    if kind != "course":
        raise ApiError("NOT_FOUND", "Course not found.", status_code=404)
    if auth.member_id is None or await access.active_grant_for(session, auth.member_id, course_id, None) is None:
        raise ApiError("ACCESS_DENIED", "Only students of this course can review it.", status_code=403)
    return auth.member_id


async def save_review(session: AsyncSession, auth: AuthContext, course_id: UUID, body: ReviewIn) -> MyReview:
    member_id = await _require_access(session, auth, course_id)
    comment = (body.comment or "").strip() or None
    await session.execute(text("""
        INSERT INTO course_reviews (class_id, student_member_id, rating, comment) VALUES (:c, :m, :r, :t)
        ON CONFLICT (class_id, student_member_id)
        DO UPDATE SET rating = EXCLUDED.rating, comment = EXCLUDED.comment, updated_at = now()
    """), {"c": course_id, "m": member_id, "r": body.rating, "t": comment})
    await recompute_rating(session, course_id)
    review = await my_review(session, auth, course_id)
    assert review is not None
    return review


async def delete_review(session: AsyncSession, auth: AuthContext, course_id: UUID) -> None:
    member_id = await _require_access(session, auth, course_id)
    await session.execute(text("DELETE FROM course_reviews WHERE class_id = :c AND student_member_id = :m"),
                          {"c": course_id, "m": member_id})
    await recompute_rating(session, course_id)


# --- the marketplace ----------------------------------------------------------------------

async def public_reviews(slug: str, cursor: str | None, limit: int) -> PublicReviewPage:
    offset = _decode_offset(cursor)
    async with AppSession() as session:
        course_id = (await session.execute(text("SELECT id FROM public_courses WHERE slug = :s"),
                                           {"s": slug})).scalar_one_or_none()
        if course_id is None:
            raise ApiError("NOT_FOUND", "Course not found.", status_code=404)
        counts = (await session.execute(text("""
            SELECT rating, count(*) AS n FROM public_course_reviews WHERE course_id = :c GROUP BY rating
        """), {"c": course_id})).all()
        rows = (await session.execute(text("""
            SELECT id, rating, comment, reviewer, instructor_reply, replied_at, created_at FROM public_course_reviews
            WHERE course_id = :c ORDER BY (comment IS NOT NULL) DESC, created_at DESC, id
            LIMIT :limit OFFSET :offset
        """), {"c": course_id, "limit": limit + 1, "offset": offset})).all()
    distribution = {stars: 0 for stars in (5, 4, 3, 2, 1)}
    for c in counts:
        distribution[c.rating] = c.n
    total = sum(distribution.values())
    average = round(sum(k * v for k, v in distribution.items()) / total, 2) if total else None
    return PublicReviewPage(
        summary=ReviewSummary(average=average, count=total, distribution=distribution),
        items=[PublicReview.model_validate(dict(r._mapping)) for r in rows[:limit]],
        next_cursor=_encode_offset(offset + limit) if len(rows) > limit else None,
    )


# --- the instructor -----------------------------------------------------------------------

async def course_reviews(session: AsyncSession, actor: Actor, course_id: UUID) -> list[StaffReview]:
    c = await courses._load(session, actor, course_id)
    rows = (await session.execute(text(_STAFF + " WHERE r.class_id = :c ORDER BY r.created_at DESC"),
                                  {"c": c.id})).all()
    return [_staff(r) for r in rows]


async def reply(session: AsyncSession, actor: Actor, review_id: UUID, body: ReplyIn) -> StaffReview:
    r = (await session.execute(text("SELECT id, class_id FROM course_reviews WHERE id = :id FOR UPDATE"),
                               {"id": review_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Review not found.", status_code=404)
    try:
        await courses._load(session, actor, r.class_id)
    except ApiError:
        raise ApiError("NOT_FOUND", "Review not found.", status_code=404) from None
    text_ = (body.reply or "").strip() or None
    await session.execute(text("""
        UPDATE course_reviews SET instructor_reply = CAST(:t AS text),
               replied_at = CASE WHEN CAST(:t AS text) IS NULL THEN NULL ELSE now() END
        WHERE id = :id
    """), {"t": text_, "id": review_id})
    await courses._audit(session, actor, "course_review.reply", "course_review", review_id, {"removed": text_ is None})
    return _staff((await session.execute(text(_STAFF + " WHERE r.id = :id"), {"id": review_id})).one())


# --- EduZone staff (admin transaction) ------------------------------------------------------

async def staff_list(session: AsyncSession, status: str | None, course_id: UUID | None) -> list[StaffReview]:
    rows = (await session.execute(text(_STAFF + """
        WHERE (CAST(:st AS text) IS NULL OR r.status = :st) AND (CAST(:c AS uuid) IS NULL OR r.class_id = :c)
        ORDER BY r.created_at DESC LIMIT 200
    """), {"st": status, "c": course_id})).all()
    return [_staff(r) for r in rows]


async def set_visibility(session: AsyncSession, review_id: UUID, body: HideIn | None) -> tuple[StaffReview, UUID]:
    """Hide (with a reason) or show again. Returns the review and its tenant, for the caller's audit row."""
    r = (await session.execute(text("SELECT id, class_id, tenant_id FROM course_reviews WHERE id = :id FOR UPDATE"),
                               {"id": review_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Review not found.", status_code=404)
    await session.execute(text("""
        UPDATE course_reviews SET status = :st, hidden_reason = :reason, updated_at = now() WHERE id = :id
    """), {"st": "hidden" if body else "visible", "reason": body.reason.strip() if body else None, "id": review_id})
    await recompute_rating(session, r.class_id)
    return _staff((await session.execute(text(_STAFF + " WHERE r.id = :id"), {"id": review_id})).one()), r.tenant_id
