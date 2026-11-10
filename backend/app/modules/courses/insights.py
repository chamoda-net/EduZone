"""Instructor analytics for one course (step C7, docs/COURSES.md section 10), from data that already exists.

Per month (Asia/Colombo) for the last N months: enrolments (paid, with a coupon, free), money from the ledger by
`order_items.class_id` (gross as sold, refunds, the organization's net after commission, fees and refunds), and
refunds. Overall: students with access, completion rate (students at 100% / students with access), rating, wishlist
count and the top coupons. The same owner/admin/teacher rule as the course builder (a teacher sees their own).
"""

from datetime import date
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.dependencies import Actor
from app.modules.courses.service import _load


class InsightMonth(BaseModel):
    month: date
    enrol_paid: int
    enrol_coupon: int                    # bought with a coupon (a sale price or a code), free ones included
    enrol_free: int                      # free course, scholarship or given by the teacher
    gross_cents: int
    refunds_cents: int
    net_cents: int
    refund_count: int


class TopCoupon(BaseModel):
    code: str
    uses: int
    discount_cents: int
    revenue_cents: int


class CourseInsights(BaseModel):
    course_id: UUID
    currency: str
    students: int                        # with access now
    completed_students: int
    completion_rate: int                 # percent, rounded down
    rating_avg: float | None
    rating_count: int
    wishlist_count: int
    totals: InsightMonth                 # the whole range (month = its first month)
    months: list[InsightMonth]           # oldest first, every month in the range
    top_coupons: list[TopCoupon]


_MONTHS = """
    WITH months AS (
        SELECT generate_series(
            date_trunc('month', now() AT TIME ZONE 'Asia/Colombo') - make_interval(months => :n - 1),
            date_trunc('month', now() AT TIME ZONE 'Asia/Colombo'), interval '1 month')::date AS month
    ),
    sales AS (
        SELECT date_trunc('month', o.paid_at AT TIME ZONE 'Asia/Colombo')::date AS month,
               count(*) FILTER (WHERE i.coupon_id IS NULL) AS enrol_paid,
               count(*) FILTER (WHERE i.coupon_id IS NOT NULL) AS enrol_coupon
        FROM order_items i JOIN orders o ON o.id = i.order_id AND o.status IN ('paid', 'refunded')
        WHERE i.class_id = :c GROUP BY 1
    ),
    gifts AS (
        SELECT date_trunc('month', g.granted_at AT TIME ZONE 'Asia/Colombo')::date AS month, count(*) AS enrol_free
        FROM access_grants g WHERE g.class_id = :c AND g.class_month_id IS NULL AND g.source <> 'purchase' GROUP BY 1
    ),
    money AS (
        SELECT date_trunc('month', lt.occurred_at AT TIME ZONE 'Asia/Colombo')::date AS month,
               SUM(CASE WHEN lt.kind = 'sale' AND (le.account = 'gateway_clearing'
                        OR (le.account = 'gateway_fees' AND le.amount_cents > 0)) THEN le.amount_cents ELSE 0 END)
                   AS gross_cents,
               -SUM(CASE WHEN lt.kind = 'refund' AND le.account = 'gateway_clearing' THEN le.amount_cents ELSE 0 END)
                   AS refunds_cents,
               -SUM(CASE WHEN le.account = 'tenant_payable' THEN le.amount_cents ELSE 0 END) AS net_cents
        FROM ledger_entries le
        JOIN ledger_transactions lt ON lt.id = le.ledger_tx_id
            AND lt.kind IN ('sale', 'refund', 'fee_settlement', 'adjustment')
        JOIN order_items i ON i.id = le.order_item_id AND i.class_id = :c
        GROUP BY 1
    ),
    refunded AS (
        SELECT date_trunc('month', r.processed_at AT TIME ZONE 'Asia/Colombo')::date AS month, count(*) AS refund_count
        FROM refunds r JOIN order_items i ON i.id = r.order_item_id AND i.class_id = :c
        WHERE r.status = 'processed' GROUP BY 1
    )
    SELECT m.month, COALESCE(s.enrol_paid, 0) AS enrol_paid, COALESCE(s.enrol_coupon, 0) AS enrol_coupon,
           COALESCE(g.enrol_free, 0) AS enrol_free, COALESCE(x.gross_cents, 0) AS gross_cents,
           COALESCE(x.refunds_cents, 0) AS refunds_cents, COALESCE(x.net_cents, 0) AS net_cents,
           COALESCE(r.refund_count, 0) AS refund_count
    FROM months m
    LEFT JOIN sales s USING (month) LEFT JOIN gifts g USING (month) LEFT JOIN money x USING (month)
    LEFT JOIN refunded r USING (month)
    ORDER BY m.month
"""


async def course_insights(session: AsyncSession, actor: Actor, course_id: UUID, months: int) -> CourseInsights:
    c = await _load(session, actor, course_id)
    rows = (await session.execute(text(_MONTHS), {"c": course_id, "n": months})).all()
    series = [InsightMonth(month=r.month, enrol_paid=r.enrol_paid, enrol_coupon=r.enrol_coupon,
                           enrol_free=r.enrol_free, gross_cents=int(r.gross_cents), refunds_cents=int(r.refunds_cents),
                           net_cents=int(r.net_cents), refund_count=r.refund_count) for r in rows]
    totals = InsightMonth(month=series[0].month, **{
        f: sum(getattr(m, f) for m in series) for f in InsightMonth.model_fields if f != "month"})
    people = (await session.execute(text("""
        WITH total AS (SELECT count(*) AS n FROM lessons WHERE class_id = :c AND is_published AND section_id IS NOT NULL),
        students AS (
            SELECT DISTINCT g.student_member_id AS m FROM access_grants g
            WHERE g.class_id = :c AND g.class_month_id IS NULL AND g.revoked_at IS NULL
              AND (g.expires_at IS NULL OR g.expires_at > now())
        ),
        done AS (
            SELECT s.m FROM students s
            JOIN lesson_completions lc ON lc.student_member_id = s.m
            JOIN lessons l ON l.id = lc.lesson_id AND l.class_id = :c AND l.is_published AND l.section_id IS NOT NULL
            GROUP BY s.m HAVING count(*) >= (SELECT n FROM total) AND (SELECT n FROM total) > 0
        )
        SELECT (SELECT count(*) FROM students) AS students, (SELECT count(*) FROM done) AS completed,
               wishlist_count(:c) AS saved
    """), {"c": course_id})).one()
    coupons = (await session.execute(text("""
        SELECT k.code::text AS code, count(*) AS uses, COALESCE(sum(i.discount_cents), 0) AS discount_cents,
               COALESCE(sum(i.amount_cents), 0) AS revenue_cents
        FROM order_items i JOIN orders o ON o.id = i.order_id AND o.status IN ('paid', 'refunded')
        JOIN coupons k ON k.id = i.coupon_id
        WHERE i.class_id = :c GROUP BY k.code ORDER BY uses DESC, k.code LIMIT 5
    """), {"c": course_id})).all()
    return CourseInsights(
        course_id=course_id, currency=c.currency, students=people.students, completed_students=people.completed,
        completion_rate=(people.completed * 100 // people.students) if people.students else 0,
        rating_avg=float(c.rating_avg) if c.rating_avg is not None else None, rating_count=c.rating_count,
        wishlist_count=people.saved, totals=totals, months=series,
        top_coupons=[TopCoupon(code=r.code, uses=r.uses, discount_cents=int(r.discount_cents),
                               revenue_cents=int(r.revenue_cents)) for r in coupons],
    )
