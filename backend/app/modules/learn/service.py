"""The student area (`/learn`): one account, every teacher (migration phase 3).

Two ways in, both read-safe:
- Lists across tenants (memberships, payments) run in a user transaction: no tenant, and RLS shows
  only this user's own rows (migration 0006).
- Anything about a class, month, lesson, resource or order first finds that entity's tenant
  (resolve_entity_tenant), then runs in that tenant's transaction with the student's member row
  there, so the access rule and every write work exactly as on a tenant's own site.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.tenancy import tenant_transaction, user_transaction
from app.modules.auth import repository as auth_repo
from app.modules.auth.dependencies import AuthContext, UserContext, current_member
from app.modules.checkout.schemas import OrderItemOut, OrderOut
from app.modules.learn.schemas import MonthToPay, MyRequest, Today, UpcomingLesson
from app.modules.learning import repository as learning_repo
from app.modules.learning import service as learning
from app.modules.learning.access import ACTIVE_GRANT, LESSON_UNLOCKED
from app.modules.learning.schemas import MyClass, OrgRef

Kind = Literal["class", "month", "lesson", "resource", "order"]
_LABEL = {"class": "Class", "month": "Month", "lesson": "Lesson", "resource": "File", "order": "Order"}


@asynccontextmanager
async def in_tenant_of(
    kind: Kind, entity_id: UUID, user: UserContext
) -> AsyncIterator[tuple[AsyncSession, AuthContext, OrgRef]]:
    """The tenant transaction of the class/lesson/... and the user's membership there (or none)."""
    async with AppSession() as s:
        tenant_id = (await s.execute(text("SELECT resolve_entity_tenant(:k, :id)"),
                                     {"k": kind, "id": entity_id})).scalar_one_or_none()
    if tenant_id is None:
        raise ApiError("NOT_FOUND", f"{_LABEL[kind]} not found.", status_code=404)
    async with tenant_transaction(tenant_id) as session:
        org = (await session.execute(text("SELECT slug, name FROM tenants WHERE id = current_tenant_id()"))).one()
        auth = await current_member(user, session)
        yield session, auth, OrgRef(slug=org.slug, name=org.name)


async def _memberships(user: UserContext) -> list[Any]:
    async with user_transaction(user.user_id) as session:
        return await auth_repo.memberships(session)


async def _per_tenant(user: UserContext) -> AsyncIterator[tuple[AsyncSession, UUID, OrgRef]]:
    """Each tenant where the user is a member, in its own tenant transaction."""
    for m in await _memberships(user):
        async with tenant_transaction(m.tenant_id) as session:
            yield session, m.member_id, OrgRef(slug=m.slug, name=m.name)


# --- across tenants -----------------------------------------------------------------------


async def my_classes(user: UserContext) -> list[MyClass]:
    out: list[MyClass] = []
    async for session, member_id, org in _per_tenant(user):
        auth = AuthContext(user.user_id, member_id, "student", user.session_id)
        for c in await learning.my_classes(session, auth):
            out.append(c.model_copy(update={"klass": c.klass.model_copy(update={"org": org})}))
    return sorted(out, key=lambda c: c.enrolled_at, reverse=True)


_UPCOMING = f"""
    SELECT l.id AS lesson_id, l.title, l.lesson_type, l.scheduled_at, l.duration_minutes,
           c.id AS class_id, c.title AS class_title, {LESSON_UNLOCKED} AS unlocked,
           (now() >= l.scheduled_at - interval '15 minutes'
            AND now() <= l.scheduled_at + make_interval(mins => COALESCE(l.duration_minutes, 120))) AS live_now
    FROM lessons l JOIN classes c ON c.id = l.class_id
    WHERE l.is_published AND c.status <> 'draft' AND l.lesson_type = 'live' AND l.scheduled_at IS NOT NULL
      AND l.scheduled_at >= now() - make_interval(mins => COALESCE(l.duration_minutes, 120))
      AND l.scheduled_at < now() + make_interval(days => :days)
      AND (EXISTS (SELECT 1 FROM class_enrollments e WHERE e.class_id = c.id
                   AND e.student_member_id = :member_id AND e.status = 'active')
           OR {LESSON_UNLOCKED})
    ORDER BY l.scheduled_at
    LIMIT 100
"""

_TO_PAY = f"""
    SELECT c.id AS class_id, c.title AS class_title, m.id AS month_id, m.month_start,
           COALESCE(m.fee_cents, c.monthly_fee_cents) AS fee_cents,
           (m.status = 'closed') AS approved_late
    FROM class_months m
    JOIN classes c ON c.id = m.class_id
    JOIN class_enrollments e ON e.class_id = c.id AND e.student_member_id = :member_id AND e.status = 'active'
    WHERE c.pricing_model = 'monthly' AND c.status = 'published'
      AND NOT EXISTS (SELECT 1 FROM access_grants g WHERE g.student_member_id = :member_id
                      AND g.class_month_id = m.id AND {ACTIVE_GRANT})
      AND (m.status = 'open'
           OR (m.status = 'closed' AND EXISTS (SELECT 1 FROM late_month_requests r WHERE r.class_month_id = m.id
                                              AND r.student_member_id = :member_id AND r.status = 'approved')))
      AND COALESCE(m.fee_cents, c.monthly_fee_cents, 0) > 0
    ORDER BY m.month_start
"""


async def _upcoming(session: AsyncSession, member_id: UUID, org: OrgRef, days: int) -> list[UpcomingLesson]:
    rows = (await session.execute(text(_UPCOMING), {"member_id": member_id, "days": days})).all()
    return [UpcomingLesson(**r._mapping, org=org) for r in rows]


async def schedule(user: UserContext, days: int) -> list[UpcomingLesson]:
    out: list[UpcomingLesson] = []
    async for session, member_id, org in _per_tenant(user):
        out.extend(await _upcoming(session, member_id, org, days))
    return sorted(out, key=lambda lesson: lesson.scheduled_at)


async def today(user: UserContext) -> Today:
    live: list[UpcomingLesson] = []
    to_pay: list[MonthToPay] = []
    pending = classes = 0
    async for session, member_id, org in _per_tenant(user):
        live.extend(await _upcoming(session, member_id, org, 7))
        currency = (await session.execute(text("SELECT currency FROM tenants WHERE id = current_tenant_id()"))).scalar_one()
        for r in (await session.execute(text(_TO_PAY), {"member_id": member_id})).all():
            to_pay.append(MonthToPay(**r._mapping, currency=currency, org=org))
        counts = (await session.execute(text("""
            SELECT (SELECT count(*) FROM late_month_requests WHERE student_member_id = :m AND status = 'pending') AS pending,
                   (SELECT count(*) FROM class_enrollments WHERE student_member_id = :m AND status = 'active') AS classes
        """), {"m": member_id})).one()
        pending += counts.pending
        classes += counts.classes
    return Today(next_live=sorted(live, key=lambda lesson: lesson.scheduled_at)[:5],
                 to_pay=sorted(to_pay, key=lambda m: m.month_start), pending_requests=pending, classes=classes)


async def my_requests(user: UserContext) -> list[MyRequest]:
    out: list[MyRequest] = []
    async for session, member_id, org in _per_tenant(user):
        rows = (await session.execute(text("""
            SELECT r.id, r.status, r.student_note, r.decision_note, r.created_at,
                   m.id AS month_id, m.month_start, c.id AS class_id, c.title AS class_title
            FROM late_month_requests r
            JOIN class_months m ON m.id = r.class_month_id
            JOIN classes c ON c.id = m.class_id
            WHERE r.student_member_id = :m
        """), {"m": member_id})).all()
        out.extend(MyRequest(**r._mapping, org=org) for r in rows)
    return sorted(out, key=lambda r: r.created_at, reverse=True)


async def my_payments(user: UserContext) -> list[OrderOut]:
    """Every order across tenants, from the user's own rows only (user-scoped RLS)."""
    async with user_transaction(user.user_id) as session:
        rows = (await session.execute(text("""
            SELECT o.id, o.order_no, o.status, o.currency, o.total_cents, o.created_at, o.paid_at, o.checkout_id,
                   i.id AS item_id, i.class_id, i.class_month_id, i.description, i.amount_cents,
                   t.slug AS org_slug, t.name AS org_name,
                   (SELECT p.method FROM payments p WHERE p.order_id = o.id AND p.status = 'succeeded' LIMIT 1) AS method,
                   (SELECT p.card_last4 FROM payments p WHERE p.order_id = o.id AND p.status = 'succeeded' LIMIT 1)
                       AS card_last4
            FROM orders o
            JOIN order_items i ON i.order_id = o.id
            JOIN tenants t ON t.id = o.tenant_id
            WHERE o.status <> 'pending'
            ORDER BY o.created_at DESC
            LIMIT 200
        """))).all()
    return [
        OrderOut(
            id=r.id, order_no=r.order_no, status=r.status, currency=r.currency, total_cents=r.total_cents,
            created_at=r.created_at, paid_at=r.paid_at, method=r.method, card_last4=r.card_last4,
            checkout_id=r.checkout_id,
            item=OrderItemOut(id=r.item_id, class_id=r.class_id, class_slug=None, class_month_id=r.class_month_id,
                              description=r.description, amount_cents=r.amount_cents),
            org=OrgRef(slug=r.org_slug, name=r.org_name),
        )
        for r in rows
    ]


async def class_slug(session: AsyncSession, class_id: UUID) -> str:
    slug = (await session.execute(text("SELECT slug FROM classes WHERE id = :id"), {"id": class_id})).scalar_one()
    return str(slug)


async def month_class(session: AsyncSession, month_id: UUID) -> Any:
    return await learning_repo.month_with_class(session, month_id)
