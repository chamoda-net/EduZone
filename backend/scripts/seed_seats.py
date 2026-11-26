"""A class with limited seats for the demo institute (local development and the browser tests only).

    python scripts/seed_seats.py      (after scripts/seed_demo.py; set SEATS_ENABLED=true to change its settings)

"2027 A/L Physics - Small Group": 4 seats this month. Two students have paid-for access, one returning student's seat is
kept, one returning student's seat was released, so one seat is free. Running it again puts it back like that (requests,
notify list, decisions and unfinished payments of this class are cleared; nothing paid is touched).
Runs as eduzone_admin. Never run it against production.
"""

import asyncio
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AdminSession, dispose_engines
from seed_demo import STUDENT_PHONE

SLUG = "2027-al-physics-small-group"
# The third is the demo student of seed_demo.py: the returning student whose seat is kept.
STUDENTS = ("Amaya Fernando", "Dinuka Jayasinghe", "Nimali Perera", "Kavindu Bandara")


async def _one(s: AsyncSession, sql: str, **params: object) -> object:
    return (await s.execute(text(sql), params)).scalar_one()


async def _class(s: AsyncSession, tenant: object) -> object:
    found = (await s.execute(text("SELECT id FROM classes WHERE tenant_id = :t AND slug = :s"),
                             {"t": tenant, "s": SLUG})).scalar_one_or_none()
    if found is None:
        found = await _one(s, """
            INSERT INTO classes (tenant_id, teacher_member_id, title, slug, description, subject, subject_id, exam,
                                 batch_year, medium, pricing_model, monthly_fee_cents, status, cover_image_url)
            SELECT c.tenant_id, c.teacher_member_id, '2027 A/L Physics - Small Group', :slug,
                   'A small group for structured questions: four seats, every paper marked.', c.subject, c.subject_id,
                   c.exam, c.batch_year, c.medium, 'monthly', 350000, 'published', c.cover_image_url
            FROM classes c WHERE c.tenant_id = :t AND c.slug = '2027-al-physics-theory' RETURNING id
        """, t=tenant, slug=SLUG)
    await s.execute(text("""
        UPDATE classes SET seat_limit = 4, show_seat_count = true, registration = 'open', starts_on = NULL,
                           registration_after_start = NULL, renewal_day = 7, status = 'published'
        WHERE id = :c
    """), {"c": found})
    return found


async def _month(s: AsyncSession, tenant: object, cls: object, start: date, status: str) -> object:
    return await _one(s, """
        INSERT INTO class_months (tenant_id, class_id, month_start, status) VALUES (:t, :c, :d, :st)
        ON CONFLICT (class_id, month_start) DO UPDATE SET status = EXCLUDED.status RETURNING id
    """, t=tenant, c=cls, d=start, st=status)


async def seed() -> None:
    if get_settings().environment != "local":
        raise SystemExit("seed_seats.py runs only with ENVIRONMENT=local")
    async with AdminSession() as s, s.begin():
        tenant = await _one(s, "SELECT id FROM tenants WHERE slug = 'demo'")
        cls = await _class(s, tenant)
        this: date = await _one(s, "SELECT date_trunc('month', now() AT TIME ZONE 'Asia/Colombo')::date")  # type: ignore[assignment]
        last = date(this.year - (this.month == 1), (this.month - 2) % 12 + 1, 1)
        await s.execute(text("UPDATE class_months SET status = 'closed' WHERE class_id = :c"), {"c": cls})
        before, now = await _month(s, tenant, cls, last, "closed"), await _month(s, tenant, cls, this, "open")
        await s.execute(text("UPDATE class_months SET opened_at = now() - interval '40 days' WHERE id = :m"), {"m": before})
        await s.execute(text("""
            UPDATE class_months SET opened_at = now() - interval '1 hour', renew_until = now() + interval '3 days'
            WHERE id = :m
        """), {"m": now})
        for table in ("seat_requests", "seat_waits", "seat_keeps"):
            await s.execute(text(f"DELETE FROM {table} WHERE class_id = :c"), {"c": cls})
        await s.execute(text("""
            UPDATE orders SET status = 'failed' WHERE status = 'pending' AND id IN
                (SELECT order_id FROM order_items WHERE class_id = :c)
        """), {"c": cls})
        # Seats the browser tests gave or sold are taken back; the demo students' are set below.
        await s.execute(text("UPDATE access_grants SET revoked_at = now(), revoke_reason = 'demo reset' "
                             "WHERE class_id = :c AND revoked_at IS NULL"), {"c": cls})
        teacher = await _one(s, "SELECT teacher_member_id FROM classes WHERE id = :c", c=cls)
        for i, name in enumerate(STUDENTS):
            user = await _one(s, """
                INSERT INTO users (phone, full_name, phone_verified_at) VALUES (:p, :n, now())
                ON CONFLICT (phone) DO UPDATE SET full_name = EXCLUDED.full_name RETURNING id
            """, p=STUDENT_PHONE if i == 2 else f"+9477000010{i}", n=name)
            member = await _one(s, """
                INSERT INTO tenant_members (tenant_id, user_id, role) VALUES (:t, :u, 'student')
                ON CONFLICT (tenant_id, user_id) DO UPDATE SET status = 'active' RETURNING id
            """, t=tenant, u=user)
            await s.execute(text("""
                INSERT INTO class_enrollments (tenant_id, class_id, student_member_id, enrolled_at)
                VALUES (:t, :c, :m, now() - interval '30 days')
                ON CONFLICT (class_id, student_member_id) DO UPDATE SET status = 'active', enrolled_at = EXCLUDED.enrolled_at
            """), {"t": tenant, "c": cls, "m": member})
            for month, ago in ((before, "20 days"), *(((now, "30 minutes"),) if i < 2 else ())):
                await s.execute(text(f"""
                    INSERT INTO access_grants (tenant_id, student_member_id, class_id, class_month_id, source, granted_by,
                                               granted_at)
                    VALUES (:t, :m, :c, :mo, 'manual', :by, now() - interval '{ago}')
                """), {"t": tenant, "m": member, "c": cls, "mo": month, "by": teacher})
            if i == 3:
                await s.execute(text("""
                    INSERT INTO seat_keeps (tenant_id, class_id, class_month_id, student_member_id, action, decided_by)
                    VALUES (:t, :c, :mo, :m, 'release', :by)
                """), {"t": tenant, "c": cls, "mo": now, "m": member, "by": teacher})
    print("seeded the small-group class with seats")


async def main() -> None:
    try:
        await seed()
    finally:
        await dispose_engines()


if __name__ == "__main__":
    asyncio.run(main())
