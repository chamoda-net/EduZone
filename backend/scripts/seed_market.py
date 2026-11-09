"""More demo content for the marketplace (local development only).

    python scripts/seed_market.py      (after scripts/seed_demo.py)

Adds an individual teacher's organization (`dilini-maths`) with two classes, and a chemistry teacher
at the demo institute, each with months, a live lesson and a teacher profile; and two published courses
(docs/COURSES.md) with sections, video lectures, an article, free previews and a promo video (the videos play
from DEV_VIDEO_STREAM_URL). Safe to run again.
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


async def _course(s: AsyncSession, tenant: object, teacher: object, *, slug: str, category: str, price: int | None,
                  title: str, subtitle: str, level: str, language: str, objectives: list[str],
                  requirements: list[str], audience: list[str],
                  sections: list[tuple[str, list[tuple[str, str, bool]]]]) -> None:
    """A published course with its curriculum; every video lecture gets a ready 10-minute video."""
    if (await s.execute(text("SELECT 1 FROM classes WHERE kind = 'course' AND slug = :s"), {"s": slug})).first():
        return
    await s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
    description = (f"{subtitle}. Short lessons, worked examples and a clear plan, so every hour you spend turns into "
                   "marks. Watch on your phone, at your pace, as many times as you like. ") * 4

    async def video(name: str) -> object:
        return await _one(s, """
            INSERT INTO media_assets (tenant_id, uploaded_by, kind, provider, external_id, original_filename,
                                      mime_type, size_bytes, duration_seconds, status)
            VALUES (:t, :m, 'video', 'bunny_stream', :x, :n, 'video/mp4', 60000000, 600, 'ready') RETURNING id""",
                          t=tenant, m=teacher, x=f"demo-course-{slug}-{name}", n=f"{name}.mp4")

    course = await _one(s, """
        INSERT INTO classes (tenant_id, kind, teacher_member_id, title, slug, subtitle, description, category_id,
                             level, medium, pricing_model, one_time_price_cents, allow_late_months,
                             learning_objectives, requirements, target_audience, promo_media_id, welcome_message,
                             completion_message, status, first_published_at)
        VALUES (:t, 'course', :m, :title, :slug, :sub, :d, (SELECT id FROM course_categories WHERE slug = :cat),
                :lvl, :lang, :pm, :price, false, :obj, :req, :aud, :promo, 'Welcome! Start with the first lecture.',
                'Well done, you finished the course!', 'published', now())
        RETURNING id""", t=tenant, m=teacher, title=title, slug=slug, sub=subtitle, d=description, cat=category,
                        lvl=level, lang=language, pm="one_time" if price else "free", price=price, obj=objectives,
                        req=requirements, aud=audience, promo=await video("promo"))
    n = 0
    for si, (section_title, lectures) in enumerate(sections):
        section = await _one(s, """INSERT INTO course_sections (tenant_id, class_id, title, sort_order)
                                   VALUES (:t, :c, :ti, :o) RETURNING id""", t=tenant, c=course, ti=section_title, o=si)
        for li, (lecture_title, kind, preview) in enumerate(lectures):
            n += 1
            body = f"# {lecture_title}\n\nRead this before the next video." if kind == "article" else None
            lesson = await _one(s, """
                INSERT INTO lessons (tenant_id, class_id, section_id, title, lesson_type, article_body, sort_order,
                                     is_free_preview, is_published)
                VALUES (:t, :c, :sec, :ti, :k, :body, :o, :p, true) RETURNING id""", t=tenant, c=course, sec=section,
                                ti=lecture_title, k=kind, body=body, o=li, p=preview)
            if kind == "recorded":
                await s.execute(text("""INSERT INTO lesson_resources (tenant_id, lesson_id, media_asset_id, title)
                                        VALUES (:t, :l, :a, :ti)"""),
                                {"t": tenant, "l": lesson, "a": await video(f"lecture-{n}"), "ti": lecture_title})
    await s.execute(text("""
        UPDATE classes c SET
            lecture_count = (SELECT count(*) FROM lessons l WHERE l.class_id = c.id AND l.is_published),
            total_video_seconds = (SELECT COALESCE(sum(a.duration_seconds), 0) FROM lessons l
                                   JOIN lesson_resources r ON r.lesson_id = l.id
                                   JOIN media_assets a ON a.id = r.media_asset_id
                                   WHERE l.class_id = c.id AND l.is_published)
        WHERE c.id = :c"""), {"c": course})


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

        kasun = await _one(s, """SELECT m.id FROM tenant_members m JOIN users u ON u.id = m.user_id
                                  WHERE m.tenant_id = :t AND u.phone = '+94770000002'""", t=demo)
        await s.execute(text("""UPDATE teacher_profiles SET
                bio = COALESCE(bio, 'Physics teacher for 15 years. I make mechanics and electricity click.'),
                headline = COALESCE(headline, 'B.Sc Physics · 15 years teaching A/L')
            WHERE user_id = (SELECT user_id FROM tenant_members WHERE id = :m)"""), {"m": kasun})
        await _course(s, demo, kasun, slug="al-physics-problem-solving", category="exam-skills", price=300000,
                      title="A/L Physics: Problem Solving Masterclass",
                      subtitle="Crack structured and essay questions with a method that works every time",
                      level="intermediate", language="si",
                      objectives=["Break any mechanics problem into steps", "Pick the right equation in seconds",
                                  "Write full-mark answers to structured questions",
                                  "Avoid the ten most common mistakes"],
                      requirements=["Grade 12 or 13 physics syllabus"],
                      audience=["A/L physics students", "Repeat candidates"],
                      sections=[("Getting started", [("How this course works", "recorded", True),
                                                     ("Your study plan", "article", False)]),
                                ("Mechanics", [("Forces without fear", "recorded", False),
                                               ("Momentum problems", "recorded", False),
                                               ("Circular motion", "recorded", False)]),
                                ("Electricity", [("Circuits step by step", "recorded", False),
                                                 ("Past paper walkthrough", "recorded", False)])])
        await _course(s, dilini_org, dilini, slug="maths-shortcuts-free", category="exam-skills", price=None,
                      title="Mental Maths Shortcuts (Free)",
                      subtitle="Ten tricks that save minutes in every O/L and A/L paper",
                      level="beginner", language="en",
                      objectives=["Multiply two-digit numbers in your head", "Check answers in seconds",
                                  "Estimate before you calculate", "Handle fractions without fear"],
                      requirements=["No prior experience needed"], audience=["O/L and A/L students"],
                      sections=[("Shortcuts", [("Multiplying by 11", "recorded", True),
                                               ("Squaring numbers ending in 5", "recorded", True),
                                               ("Quick checks", "recorded", False),
                                               ("Estimation", "recorded", False),
                                               ("Cheat sheet", "article", False)])])
    print("marketplace demo: dilini-maths (2 classes), Ruwan Silva at demo (1 class), 2 courses")


async def main() -> None:
    try:
        await seed()
    finally:
        await dispose_engines()


if __name__ == "__main__":
    asyncio.run(main())
