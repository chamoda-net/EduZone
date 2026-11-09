"""Courses, step C2 (docs/COURSES.md): the public read path for courses.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-09

Like the tuition views of migration 0007: views owned by eduzone_admin (BYPASSRLS) that expose public fields only,
SELECT-only for the app role. Never relaxed tenant RLS.
- public_courses: published courses of active, listed organizations, in an active category, whose instructor has a
  public profile. Landing-page fields, length, rating, students (active course grants), instructor card fields.
- public_course_sections / public_course_lectures: the curriculum outline of those courses. Published lectures
  only; titles, types, order, free-preview flag and video length. Never article bodies, lecture descriptions or
  files (tests/test_market_courses.py checks).
- public_course_categories: active categories (an inactive parent hides its children) with course counts.
- public_instructors: everyone with a public course or class: one page per person (/instructor/<slug>).
"""

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | None = None
depends_on: str | None = None

_ACTIVE_CATEGORY = """
SELECT cc.* FROM course_categories cc
LEFT JOIN course_categories p ON p.id = cc.parent_id
WHERE cc.is_active AND (cc.parent_id IS NULL OR p.is_active)
"""

_VIEWS = (
    ("public_courses", f"""
CREATE VIEW public_courses AS
SELECT c.id, c.slug, c.title, c.subtitle, c.description, c.level, c.medium AS language, c.cover_image_url,
       c.pricing_model, c.one_time_price_cents, t.currency, c.learning_objectives, c.requirements, c.target_audience,
       c.total_video_seconds, c.lecture_count, c.rating_avg, c.rating_count, c.first_published_at, c.updated_at,
       (c.promo_media_id IS NOT NULL AND EXISTS (SELECT 1 FROM media_assets a WHERE a.id = c.promo_media_id
                                                 AND a.kind = 'video' AND a.status = 'ready')) AS has_promo,
       t.id AS tenant_id, t.slug AS org_slug, t.name AS org_name, t.org_type,
       cat.id AS category_id, cat.slug AS category_slug, cat.name_en AS category_name,
       parent.slug AS parent_category_slug, parent.name_en AS parent_category_name,
       tp.slug AS teacher_slug, tp.display_name AS teacher_name, tp.photo_url AS teacher_photo_url,
       tp.headline AS teacher_headline,
       (SELECT count(DISTINCT g.student_member_id) FROM access_grants g
        WHERE g.class_id = c.id AND g.class_month_id IS NULL AND g.revoked_at IS NULL
          AND (g.expires_at IS NULL OR g.expires_at > now())) AS students,
       to_tsvector('simple', coalesce(c.title, '') || ' ' || coalesce(c.subtitle, '') || ' ' || cat.name_en || ' '
                   || tp.display_name || ' ' || coalesce(c.description, '')) AS search
FROM classes c
JOIN tenants t ON t.id = c.tenant_id AND t.status = 'active' AND t.is_listed
JOIN ({_ACTIVE_CATEGORY}) cat ON cat.id = c.category_id
LEFT JOIN course_categories parent ON parent.id = cat.parent_id
JOIN tenant_members tm ON tm.tenant_id = c.tenant_id AND tm.id = c.teacher_member_id
JOIN teacher_profiles tp ON tp.user_id = tm.user_id
WHERE c.kind = 'course' AND c.status = 'published'
"""),
    ("public_course_sections", """
CREATE VIEW public_course_sections AS
SELECT s.id, s.class_id AS course_id, s.title, s.sort_order
FROM course_sections s JOIN public_courses pc ON pc.id = s.class_id
"""),
    ("public_course_lectures", """
CREATE VIEW public_course_lectures AS
SELECT l.id, l.class_id AS course_id, l.section_id, l.title, l.lesson_type, l.sort_order, l.is_free_preview,
       COALESCE((SELECT sum(a.duration_seconds) FROM lesson_resources r
                 JOIN media_assets a ON a.id = r.media_asset_id AND a.kind = 'video' AND a.status = 'ready'
                 WHERE r.lesson_id = l.id), 0)::int AS video_seconds
FROM lessons l JOIN public_courses pc ON pc.id = l.class_id
WHERE l.is_published AND l.section_id IS NOT NULL
"""),
    ("public_course_categories", f"""
CREATE VIEW public_course_categories AS
SELECT cat.id, cat.parent_id, cat.slug, cat.name_en, cat.name_si, cat.name_ta, cat.sort_order,
       (SELECT count(*) FROM public_courses pc
        WHERE pc.category_id = cat.id
           OR pc.category_id IN (SELECT id FROM course_categories WHERE parent_id = cat.id)) AS course_count
FROM ({_ACTIVE_CATEGORY}) cat
"""),
    ("public_instructors", """
CREATE VIEW public_instructors AS
SELECT tp.slug, tp.display_name, tp.headline, tp.bio, tp.photo_url, tp.highlights,
       (SELECT count(*) FROM public_courses pc WHERE pc.teacher_slug = tp.slug) AS course_count,
       (SELECT count(*) FROM public_classes pc WHERE pc.teacher_slug = tp.slug) AS class_count,
       COALESCE((SELECT sum(pc.students) FROM public_courses pc WHERE pc.teacher_slug = tp.slug), 0)
         + COALESCE((SELECT sum(pc.students) FROM public_classes pc WHERE pc.teacher_slug = tp.slug), 0) AS students,
       (SELECT round(avg(pc.rating_avg), 2) FROM public_courses pc
        WHERE pc.teacher_slug = tp.slug AND pc.rating_avg IS NOT NULL) AS rating_avg
FROM teacher_profiles tp
WHERE EXISTS (SELECT 1 FROM public_courses pc WHERE pc.teacher_slug = tp.slug)
   OR EXISTS (SELECT 1 FROM public_classes pc WHERE pc.teacher_slug = tp.slug)
"""),
)


def upgrade() -> None:
    for name, sql in _VIEWS:
        op.execute(sql)
        op.execute(f"ALTER VIEW {name} OWNER TO eduzone_admin")
        op.execute(f"GRANT SELECT ON {name} TO eduzone_app")
    # Browsing courses by category, newest and length.
    op.execute("CREATE INDEX idx_classes_course_published ON classes (first_published_at DESC) "
               "WHERE kind = 'course' AND status = 'published'")


def downgrade() -> None:
    op.execute("DROP INDEX idx_classes_course_published")
    for name, _ in reversed(_VIEWS):
        op.execute(f"DROP VIEW {name}")
