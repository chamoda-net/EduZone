"""THE access rule (CLAUDE.md section 6). Every place that decides whether a student may
open a lesson goes through this module; nothing else re-implements it.

A student can open a lesson if the lesson is published, its class is not a draft, and:
  * the lesson is a free preview, or
  * monthly class: an active grant for (student, lesson.class_month_id), or
  * one-time / free class: an active grant for (student, class_id) with no month.
Active = not revoked and not expired.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

ACTIVE_GRANT = "g.revoked_at IS NULL AND (g.expires_at IS NULL OR g.expires_at > now())"

# SQL boolean for lesson `l` (joined with its class `c`) and student :member_id.
LESSON_UNLOCKED = f"""(
    l.is_published AND c.status <> 'draft' AND (
        l.is_free_preview OR EXISTS (
            SELECT 1 FROM access_grants g
            WHERE g.student_member_id = :member_id AND {ACTIVE_GRANT}
              AND (   (l.class_month_id IS NOT NULL AND g.class_month_id = l.class_month_id)
                   OR (l.class_month_id IS NULL AND g.class_id = l.class_id AND g.class_month_id IS NULL))
        )
    )
)"""


async def lesson_for_student(session: AsyncSession, member_id: UUID, lesson_id: UUID) -> Any:
    """The lesson with its class and an `unlocked` flag, or None if a student can't even
    see it (unpublished lesson or draft class)."""
    return (await session.execute(text(f"""
        SELECT l.*, c.slug AS class_slug, c.title AS class_title, c.max_video_views,
               {LESSON_UNLOCKED} AS unlocked
        FROM lessons l JOIN classes c ON c.id = l.class_id
        WHERE l.id = :lesson_id AND l.is_published AND c.status <> 'draft'
    """), {"member_id": member_id, "lesson_id": lesson_id})).one_or_none()


async def class_lessons_for_student(session: AsyncSession, member_id: UUID | None, class_id: UUID) -> list[Any]:
    """Published lessons of a class with `unlocked` for this student (all locked when
    nobody is signed in, except free previews)."""
    unlocked = LESSON_UNLOCKED if member_id is not None else "(l.is_published AND l.is_free_preview)"
    return list((await session.execute(text(f"""
        SELECT l.id, l.class_month_id, l.title, l.lesson_type, l.sort_order, l.scheduled_at,
               l.duration_minutes, l.is_free_preview, {unlocked} AS unlocked
        FROM lessons l JOIN classes c ON c.id = l.class_id
        LEFT JOIN class_months m ON m.id = l.class_month_id
        WHERE l.class_id = :class_id AND l.is_published
        ORDER BY m.month_start NULLS FIRST, l.sort_order, l.created_at
    """), {"member_id": member_id, "class_id": class_id})).all())


async def active_grant_for(session: AsyncSession, member_id: UUID, class_id: UUID,
                           class_month_id: UUID | None) -> Any:
    """The active grant for a month (or, with no month, the class-level grant), if any."""
    month_match = "g.class_month_id = :month_id" if class_month_id else "g.class_month_id IS NULL"
    return (await session.execute(text(f"""
        SELECT g.id, g.source FROM access_grants g
        WHERE g.student_member_id = :member_id AND g.class_id = :class_id AND {month_match} AND {ACTIVE_GRANT}
    """), {"member_id": member_id, "class_id": class_id, "month_id": class_month_id})).one_or_none()
