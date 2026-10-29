"""Learning DB access (tenant transaction; RLS scopes every query)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.learning.access import ACTIVE_GRANT

_PUBLIC_CLASS = """
    c.id, c.slug, c.title, c.description, c.subject, c.exam, c.batch_year, c.medium, c.cover_image_url,
    c.pricing_model, c.monthly_fee_cents, c.one_time_price_cents, t.currency,
    COALESCE(tm.display_name, u.full_name) AS teacher_name
"""
_PUBLIC_FROM = """
    FROM classes c
    JOIN tenants t ON t.id = c.tenant_id
    JOIN tenant_members tm ON tm.id = c.teacher_member_id
    JOIN users u ON u.id = tm.user_id
"""


async def list_published(session: AsyncSession, *, exam: str | None, after: tuple[datetime, UUID] | None,
                         limit: int) -> list[Any]:
    return list((await session.execute(text(f"""
        SELECT {_PUBLIC_CLASS}, c.created_at {_PUBLIC_FROM}
        WHERE c.status = 'published'
          AND (CAST(:exam AS text) IS NULL OR c.exam = :exam)
          AND (CAST(:after_ts AS timestamptz) IS NULL OR (c.created_at, c.id) < (:after_ts, :after_id))
        ORDER BY c.created_at DESC, c.id DESC
        LIMIT :limit
    """), {"exam": exam, "after_ts": after[0] if after else None, "after_id": after[1] if after else None,
           "limit": limit})).all())


async def class_by_slug(session: AsyncSession, slug: str, *, published_only: bool) -> Any:
    """Published classes for anyone; archived ones too for students who already have access."""
    statuses = "('published')" if published_only else "('published', 'archived')"
    return (await session.execute(text(f"""
        SELECT {_PUBLIC_CLASS}, c.allow_late_months, c.status {_PUBLIC_FROM}
        WHERE c.slug = :slug AND c.status IN {statuses}
    """), {"slug": slug})).one_or_none()


async def class_months(session: AsyncSession, class_id: UUID) -> list[Any]:
    return list((await session.execute(text("""
        SELECT m.id, m.month_start, COALESCE(m.fee_cents, c.monthly_fee_cents, 0) AS fee_cents, m.status
        FROM class_months m JOIN classes c ON c.id = m.class_id
        WHERE m.class_id = :c ORDER BY m.month_start
    """), {"c": class_id})).all())


# --- per student --------------------------------------------------------------------

async def enrollment(session: AsyncSession, member_id: UUID, class_id: UUID) -> Any:
    return (await session.execute(text("""
        SELECT id, status, enrolled_at FROM class_enrollments
        WHERE class_id = :c AND student_member_id = :m
    """), {"c": class_id, "m": member_id})).one_or_none()


async def upsert_enrollment(session: AsyncSession, member_id: UUID, class_id: UUID) -> None:
    await session.execute(text("""
        INSERT INTO class_enrollments (tenant_id, class_id, student_member_id)
        VALUES (current_tenant_id(), :c, :m)
        ON CONFLICT (class_id, student_member_id)
        DO UPDATE SET status = 'active', left_at = NULL, enrolled_at = now()
        WHERE class_enrollments.status <> 'active'
    """), {"c": class_id, "m": member_id})


async def leave(session: AsyncSession, member_id: UUID, class_id: UUID) -> None:
    await session.execute(text("""
        UPDATE class_enrollments SET status = 'left', left_at = now()
        WHERE class_id = :c AND student_member_id = :m AND status = 'active'
    """), {"c": class_id, "m": member_id})


async def month_grants(session: AsyncSession, member_id: UUID, class_id: UUID) -> set[UUID | None]:
    """Months (and None for a class-level grant) this student has active access to."""
    rows = (await session.execute(text(f"""
        SELECT g.class_month_id FROM access_grants g
        WHERE g.student_member_id = :m AND g.class_id = :c AND {ACTIVE_GRANT}
    """), {"m": member_id, "c": class_id})).scalars()
    return set(rows)


async def late_requests(session: AsyncSession, member_id: UUID, class_id: UUID) -> dict[UUID, str]:
    rows = (await session.execute(text("""
        SELECT r.class_month_id, r.status FROM late_month_requests r
        JOIN class_months m ON m.id = r.class_month_id
        WHERE r.student_member_id = :m AND m.class_id = :c
    """), {"m": member_id, "c": class_id})).all()
    return {r.class_month_id: r.status for r in rows}


async def my_classes(session: AsyncSession, member_id: UUID) -> list[Any]:
    return list((await session.execute(text(f"""
        SELECT {_PUBLIC_CLASS}, e.enrolled_at,
               (SELECT count(*) FROM access_grants g
                WHERE g.student_member_id = :m AND g.class_id = c.id AND {ACTIVE_GRANT}) AS unlocked_months
        {_PUBLIC_FROM}
        JOIN class_enrollments e ON e.class_id = c.id AND e.student_member_id = :m AND e.status = 'active'
        WHERE c.status IN ('published', 'archived')
        ORDER BY e.enrolled_at DESC
    """), {"m": member_id})).all())


async def month_with_class(session: AsyncSession, month_id: UUID) -> Any:
    return (await session.execute(text("""
        SELECT m.id, m.status, m.class_id, c.pricing_model, c.allow_late_months, c.status AS class_status
        FROM class_months m JOIN classes c ON c.id = m.class_id WHERE m.id = :id
    """), {"id": month_id})).one_or_none()


async def late_request(session: AsyncSession, member_id: UUID, month_id: UUID) -> Any:
    return (await session.execute(text("""
        SELECT id, status FROM late_month_requests WHERE class_month_id = :mo AND student_member_id = :m
    """), {"mo": month_id, "m": member_id})).one_or_none()


async def insert_late_request(session: AsyncSession, member_id: UUID, month_id: UUID, note: str | None) -> Any:
    return (await session.execute(text("""
        INSERT INTO late_month_requests (tenant_id, class_month_id, student_member_id, student_note)
        VALUES (current_tenant_id(), :mo, :m, :note)
        RETURNING id, class_month_id, status, student_note, decision_note, created_at
    """), {"mo": month_id, "m": member_id, "note": note})).one()


async def insert_grant(session: AsyncSession, *, member_id: UUID, class_id: UUID, month_id: UUID | None,
                       source: str, granted_by: UUID | None) -> UUID:
    return (await session.execute(text("""
        INSERT INTO access_grants (tenant_id, student_member_id, class_id, class_month_id, source, granted_by)
        VALUES (current_tenant_id(), :m, :c, :mo, :src, :by)
        RETURNING id
    """), {"m": member_id, "c": class_id, "mo": month_id, "src": source, "by": granted_by})).scalar_one()


# --- resources and views --------------------------------------------------------------

async def lesson_resources(session: AsyncSession, member_id: UUID, lesson_id: UUID) -> list[Any]:
    return list((await session.execute(text("""
        SELECT r.id, COALESCE(r.title, a.original_filename, 'File') AS title, a.kind, a.duration_seconds,
               r.is_downloadable, a.status = 'ready' AS ready, COALESCE(p.view_count, 0) AS views_used
        FROM lesson_resources r
        JOIN media_assets a ON a.id = r.media_asset_id
        LEFT JOIN lesson_progress p ON p.lesson_resource_id = r.id AND p.student_member_id = :m
        WHERE r.lesson_id = :l AND a.status <> 'deleted'
        ORDER BY r.sort_order, r.created_at
    """), {"m": member_id, "l": lesson_id})).all())


async def resource(session: AsyncSession, resource_id: UUID) -> Any:
    return (await session.execute(text("""
        SELECT r.id, r.lesson_id, r.media_asset_id FROM lesson_resources r WHERE r.id = :id
    """), {"id": resource_id})).one_or_none()


async def count_view(session: AsyncSession, member_id: UUID, resource_id: UUID, max_views: int | None) -> int | None:
    """Starts a play session: +1 view, atomically refused at the limit. Returns the new
    count, or None when the limit was already reached."""
    return (await session.execute(text("""
        INSERT INTO lesson_progress (tenant_id, student_member_id, lesson_resource_id, view_count, last_viewed_at)
        VALUES (current_tenant_id(), :m, :r, 1, now())
        ON CONFLICT (student_member_id, lesson_resource_id) DO UPDATE
           SET view_count = lesson_progress.view_count + 1, last_viewed_at = now()
         WHERE CAST(:max AS integer) IS NULL OR lesson_progress.view_count < :max
        RETURNING view_count
    """), {"m": member_id, "r": resource_id, "max": max_views})).scalar_one_or_none()


async def member_identity(session: AsyncSession, member_id: UUID) -> Any:
    return (await session.execute(text("""
        SELECT u.full_name, u.phone FROM tenant_members tm JOIN users u ON u.id = tm.user_id WHERE tm.id = :m
    """), {"m": member_id})).one()
