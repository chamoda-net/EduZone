"""More demo content for the marketplace (local development only).

    python scripts/seed_market.py      (after scripts/seed_demo.py)

Adds an individual teacher's organization (`dilini-maths`) with two classes, and a chemistry teacher
at the demo institute, each with months, a live lesson and a teacher profile. Safe to run again.
Runs as eduzone_admin. Never run it against production.
"""

import asyncio
from datetime import date

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AdminSession, dispose_engines


async def _one(s: AsyncSession, sql: str, **params: object) -> object:
    return (await s.execute(text(sql), params)).scalar_one()


async def _teacher(s: AsyncSession, tenant: object, phone: str, name: str, role: str, slug: str, headline: str,
                   bio: str, highlights: list[str]) -> object:
    user = await _one(s, """
        INSERT INTO users (phone, full_name, phone_verified_at) VALUES (:p, :n, now())
        ON CONFLICT (phone) DO UPDATE SET full_name = users.full_name RETURNING id""", p=phone, n=name)
    member = await _one(s, """
        INSERT INTO tenant_members (tenant_id, user_id, role, display_name) VALUES (:t, :u, :r, :n)
        ON CONFLICT (tenant_id, user_id) DO UPDATE SET role = EXCLUDED.role RETURNING id""",
                        t=tenant, u=user, r=role, n=name)
    await s.execute(text("""
        INSERT INTO teacher_profiles (user_id, slug, display_name, headline, bio, highlights)
        VALUES (:u, :s, :n, :h, :b, :hl)
        ON CONFLICT (user_id) DO UPDATE SET headline = EXCLUDED.headline, bio = EXCLUDED.bio,
                                            highlights = EXCLUDED.highlights
    """), {"u": user, "s": slug, "n": name, "h": headline, "b": bio, "hl": highlights})
    return member


async def _class(s: AsyncSession, tenant: object, teacher: object, *, title: str, slug: str, subject: str, exam: str,
                 year: int | None, medium: str, fee: int, description: str) -> None:
    if (await s.execute(text("SELECT 1 FROM classes WHERE tenant_id = :t AND slug = :s"), {"t": tenant, "s": slug})).first():
        return
    subject_id, subject_name = (await s.execute(text("SELECT id, name FROM subjects WHERE slug = :s"),
                                                {"s": subject})).one()
    cls = await _one(s, """
        INSERT INTO classes (tenant_id, teacher_member_id, title, slug, description, subject, subject_id, exam,
                             batch_year, medium, pricing_model, monthly_fee_cents, status)
        VALUES (:t, :m, :title, :slug, :d, :sn, :sid, :exam, :year, :medium, 'monthly', :fee, 'published')
        RETURNING id""", t=tenant, m=teacher, title=title, slug=slug, d=description, sn=subject_name, sid=subject_id,
                     exam=exam, year=year, medium=medium, fee=fee)
    for month, status in ((date(2026, 10, 1), "closed"), (date(2026, 11, 1), "open"), (date(2026, 12, 1), "upcoming")):
        month_id = await _one(s, """INSERT INTO class_months (tenant_id, class_id, month_start, status)
                                    VALUES (:t, :c, :d, :st) RETURNING id""", t=tenant, c=cls, d=month, st=status)
        await s.execute(text("""
            INSERT INTO lessons (tenant_id, class_id, class_month_id, title, lesson_type, sort_order, scheduled_at,
                                 duration_minutes, zoom_join_url, is_published, is_free_preview)
            VALUES (:t, :c, :m, 'Weekly live class', 'live', 1, (CAST(:d AS date) + time '16:00') AT TIME ZONE 'Asia/Colombo',
                    120, 'https://zoom.us/j/9876543210', true, false),
                   (:t, :c, :m, 'Model paper', 'document', 2, NULL, NULL, NULL, true, :preview)
        """), {"t": tenant, "c": cls, "m": month_id, "d": month, "preview": status == "closed"})


async def seed() -> None:
    if get_settings().environment != "local":
        raise SystemExit("seed_market only runs with ENVIRONMENT=local")
    async with AdminSession() as s, s.begin():
        demo = (await s.execute(text("SELECT id FROM tenants WHERE slug = 'demo'"))).scalar_one_or_none()
        if demo is None:
            raise SystemExit("run scripts/seed_demo.py first")
        dilini_org = await _one(s, """
            INSERT INTO tenants (name, slug, org_type) VALUES ('Dilini Fernando Maths', 'dilini-maths', 'individual')
            ON CONFLICT (slug) DO UPDATE SET name = tenants.name RETURNING id""")
        dilini = await _teacher(
            s, dilini_org, "+94770000011", "Dilini Fernando", "owner", "dilini-fernando",
            "B.Sc (Hons) Mathematics · 10 years teaching",
            "I teach Combined Maths and O/L Maths in Sinhala medium, with weekly paper classes and recorded revision.",
            ["148 A passes in 2025 A/L", "Island rank 7 student in 2024", "Author of the 'Calculus Made Simple' series"])
        await _class(s, dilini_org, dilini, title="2026 A/L Combined Maths - Theory", slug="2026-al-combined-maths",
                     subject="combined-maths", exam="al", year=2026, medium="si", fee=250000,
                     description="Full theory for the 2026 A/L: pure maths and applied, one live class every week.")
        await _class(s, dilini_org, dilini, title="2027 O/L Mathematics", slug="2027-ol-maths",
                     subject="mathematics", exam="ol", year=2027, medium="si", fee=150000,
                     description="The whole O/L syllabus with past papers every month.")
        ruwan = await _teacher(
            s, demo, "+94770000012", "Ruwan Silva", "teacher", "ruwan-silva",
            "B.Sc Chemistry · 8 years teaching",
            "Organic and physical chemistry for A/L, with a model paper every month.",
            ["92% A/B rate in 2025"])
        await _class(s, demo, ruwan, title="2027 A/L Chemistry - Theory", slug="2027-al-chemistry",
                     subject="chemistry", exam="al", year=2027, medium="en", fee=220000,
                     description="Theory and practicals for the 2027 A/L in English medium.")
        await s.execute(text("UPDATE tenants SET org_type = 'institute' WHERE id = :t"), {"t": demo})
    print("marketplace demo: dilini-maths (2 classes), Ruwan Silva at demo (1 class)")


async def main() -> None:
    try:
        await seed()
    finally:
        await dispose_engines()


if __name__ == "__main__":
    asyncio.run(main())
