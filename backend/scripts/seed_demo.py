"""Seed a demo organization for local development.

    python scripts/seed_demo.py

Creates tenant `demo` (open http://demo.localhost:3000 with BASE_DOMAIN=localhost), an owner,
a teacher and two classes. Safe to run again: an existing `demo` is left as it is, but the demo
accounts always get the sign-in details below. Runs as eduzone_admin, like other platform jobs.
Never run it against production.

Sign in with the email below and DEMO_PASSWORD (a local test value). Their phones count as
verified, so the first sign-in on a browser asks for the SMS code (SMS_PROVIDER=console logs it).
"""

import asyncio
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AdminSession, dispose_engines
from app.modules.auth.passwords import hash_password

OWNER_PHONE = "+94770000001"
TEACHER_PHONE = "+94770000002"
OWNER_EMAIL = "owner.demo@example.com"
TEACHER_EMAIL = "teacher.demo@example.com"
DEMO_PASSWORD = "Demo-pass-2026"  # local test value only


async def demo_accounts(s: AsyncSession) -> None:
    """Email + password sign-in for the demo staff (idempotent)."""
    for phone, email in ((OWNER_PHONE, OWNER_EMAIL), (TEACHER_PHONE, TEACHER_EMAIL)):
        await s.execute(text("""
            UPDATE users SET email = :e, password_hash = :h, email_verified_at = COALESCE(email_verified_at, now()),
                             phone_verified_at = COALESCE(phone_verified_at, now())
            WHERE phone = :p
        """), {"p": phone, "e": email, "h": hash_password(DEMO_PASSWORD)})


async def seed() -> None:
    if get_settings().environment != "local":
        raise SystemExit("seed_demo only runs with ENVIRONMENT=local")

    async with AdminSession() as s, s.begin():
        if (await s.execute(text("SELECT 1 FROM tenants WHERE slug = 'demo'"))).first():
            await demo_accounts(s)
            print(f"demo tenant already exists; sign-in details refreshed for {OWNER_EMAIL}, {TEACHER_EMAIL}")
            return

        async def one(sql: str, **params: object) -> object:
            return (await s.execute(text(sql), params)).scalar_one()

        tenant = await one("""INSERT INTO tenants (name, slug, org_type, primary_color)
                              VALUES ('Demo Tuition Institute', 'demo', 'institute', '#1E6FD9') RETURNING id""")

        async def member(phone: str, name: str, role: str) -> object:
            user = await one("""INSERT INTO users (phone, full_name, phone_verified_at) VALUES (:p, :n, now())
                                ON CONFLICT (phone) DO UPDATE SET full_name = users.full_name RETURNING id""",
                             p=phone, n=name)
            return await one("""INSERT INTO tenant_members (tenant_id, user_id, role, display_name)
                                VALUES (:t, :u, :r, :n) RETURNING id""", t=tenant, u=user, r=role, n=name)

        await member(OWNER_PHONE, "Demo Owner", "owner")
        teacher = await member(TEACHER_PHONE, "Kasun Perera", "teacher")

        physics = await one("""
            INSERT INTO classes (tenant_id, teacher_member_id, title, slug, subject, exam, batch_year, medium,
                                 pricing_model, monthly_fee_cents, status)
            VALUES (:t, :m, '2027 A/L Physics - Theory', '2027-al-physics-theory', 'Physics', 'al', 2027, 'si',
                    'monthly', 200000, 'published') RETURNING id""", t=tenant, m=teacher)
        for month, status in ((date(2026, 10, 1), "closed"), (date(2026, 11, 1), "open"),
                              (date(2026, 12, 1), "upcoming")):
            month_id = await one("""INSERT INTO class_months (tenant_id, class_id, month_start, status)
                                    VALUES (:t, :c, :d, :st) RETURNING id""",
                                 t=tenant, c=physics, d=month, st=status)
            await s.execute(text("""
                INSERT INTO lessons (tenant_id, class_id, class_month_id, title, lesson_type, sort_order,
                                     scheduled_at, duration_minutes, zoom_join_url, is_published)
                VALUES (:t, :c, :m, 'Live class', 'live', 1,
                        (CAST(:d AS date) + time '14:00') AT TIME ZONE 'Asia/Colombo', 120, 'https://zoom.us/j/1234567890', true),
                       (:t, :c, :m, 'Tute', 'document', 2, NULL, NULL, NULL, true)
            """), {"t": tenant, "c": physics, "m": month_id, "d": month})

        await s.execute(text("""
            INSERT INTO classes (tenant_id, teacher_member_id, title, slug, subject, exam, medium,
                                 pricing_model, one_time_price_cents, status)
            VALUES (:t, :m, 'Grade 5 Scholarship Paper Class', 'grade-5-paper-class', 'Scholarship', 'grade_5',
                    'si', 'one_time', 350000, 'draft')"""), {"t": tenant, "m": teacher})

        await demo_accounts(s)

    print(f"seeded tenant 'demo': owner {OWNER_EMAIL}, teacher {TEACHER_EMAIL} (password: DEMO_PASSWORD in this file)")


async def main() -> None:
    try:
        await seed()
    finally:
        await dispose_engines()


if __name__ == "__main__":
    asyncio.run(main())
