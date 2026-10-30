"""Marketplace (migration phase 4): subjects, teacher profiles, listing and the public read path.

Revision ID: 0007
Revises: 0006
Create Date: 2026-10-30

- subjects: EduZone-managed; slugs are the first URL segment (/physics), so they can never be a
  reserved route (is_reserved_slug()).
- classes.subject_id (backfilled from the free-text subject where it matches).
- teacher_profiles: one public profile per person (slug unique platform-wide), backfilled for everyone
  who teaches a class.
- tenants.is_listed: shown on the marketplace (approval arrives in phase 5).
- The public read path: views owned by eduzone_admin (BYPASSRLS) that expose public fields only, for
  active, listed tenants and published classes with a subject and a teacher profile. The app role may
  read the views; tenant RLS on the underlying tables is unchanged.
"""

from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | None = None
depends_on: str | None = None

# First URL segments the web app uses; a subject slug can never be one of these.
RESERVED = (
    "about", "account", "admin", "api", "assets", "cart", "checkout", "classes", "contact", "design",
    "help", "institutes", "learn", "lessons", "login", "logout", "my", "org", "payments", "privacy",
    "qr", "recover", "refund-policy", "register", "robots.txt", "search", "sitemap.xml", "static",
    "teach", "teachers", "terms", "verify-email", "verify-phone",
)

SUBJECTS = (
    ("physics", "Physics", 10), ("chemistry", "Chemistry", 20), ("biology", "Biology", 30),
    ("combined-maths", "Combined Maths", 40), ("mathematics", "Mathematics", 50), ("science", "Science", 60),
    ("ict", "ICT", 70), ("english", "English", 80), ("sinhala", "Sinhala", 90), ("tamil", "Tamil", 100),
    ("accounting", "Accounting", 110), ("economics", "Economics", 120), ("business-studies", "Business Studies", 130),
    ("history", "History", 140), ("geography", "Geography", 150), ("buddhism", "Buddhism", 160),
    ("scholarship", "Grade 5 Scholarship", 170), ("engineering-technology", "Engineering Technology", 180),
    ("science-for-technology", "Science for Technology", 190), ("agriculture", "Agriculture", 200),
)

_PUBLIC_CLASSES = """
CREATE VIEW public_classes AS
SELECT c.id, c.slug, c.title, c.description, c.exam, c.batch_year, c.medium, c.cover_image_url,
       c.pricing_model, c.monthly_fee_cents, c.one_time_price_cents, c.created_at,
       t.currency, t.id AS tenant_id, t.slug AS org_slug, t.name AS org_name, t.org_type,
       s.id AS subject_id, s.slug AS subject_slug, s.name AS subject_name,
       tp.slug AS teacher_slug, tp.display_name AS teacher_name, tp.photo_url AS teacher_photo_url,
       tp.headline AS teacher_headline,
       om.id AS open_month_id, om.month_start AS open_month_start,
       COALESCE(om.fee_cents, c.monthly_fee_cents) AS open_month_fee_cents,
       EXISTS (SELECT 1 FROM lessons l WHERE l.class_id = c.id AND l.is_published AND l.lesson_type = 'live')
           AS has_live,
       EXISTS (SELECT 1 FROM lessons l WHERE l.class_id = c.id AND l.is_published AND l.lesson_type = 'recorded')
           AS has_recorded,
       EXISTS (SELECT 1 FROM lessons l WHERE l.class_id = c.id AND l.is_published AND l.is_free_preview)
           AS has_free_preview,
       (SELECT count(*) FROM class_enrollments e WHERE e.class_id = c.id AND e.status = 'active') AS students,
       to_tsvector('simple', coalesce(c.title, '') || ' ' || s.name || ' ' || tp.display_name || ' '
                   || t.name || ' ' || coalesce(c.description, '')) AS search
FROM classes c
JOIN tenants t ON t.id = c.tenant_id AND t.status = 'active' AND t.is_listed
JOIN subjects s ON s.id = c.subject_id AND s.is_active
JOIN tenant_members tm ON tm.tenant_id = c.tenant_id AND tm.id = c.teacher_member_id
JOIN teacher_profiles tp ON tp.user_id = tm.user_id
LEFT JOIN LATERAL (
    SELECT m.id, m.month_start, m.fee_cents FROM class_months m
    WHERE m.class_id = c.id AND m.status = 'open' ORDER BY m.month_start LIMIT 1
) om ON true
WHERE c.status = 'published'
"""

_PUBLIC_VIEWS = (
    _PUBLIC_CLASSES,
    """
CREATE VIEW public_class_months AS
SELECT m.id, m.class_id, m.month_start, m.status, COALESCE(m.fee_cents, pc.monthly_fee_cents) AS fee_cents,
       pc.currency
FROM class_months m JOIN public_classes pc ON pc.id = m.class_id
""",
    """
CREATE VIEW public_lessons AS
SELECT l.id, l.class_id, l.class_month_id, l.title, l.lesson_type, l.sort_order, l.scheduled_at,
       l.duration_minutes, l.is_free_preview
FROM lessons l JOIN public_classes pc ON pc.id = l.class_id
WHERE l.is_published
""",
    """
CREATE VIEW public_teachers AS
SELECT tp.slug, tp.display_name, tp.headline, tp.bio, tp.photo_url, tp.highlights,
       count(pc.id) AS class_count,
       array_agg(DISTINCT pc.subject_slug) AS subject_slugs,
       array_agg(DISTINCT pc.subject_name) AS subject_names,
       array_agg(DISTINCT pc.medium) FILTER (WHERE pc.medium IS NOT NULL) AS mediums,
       sum(pc.students) AS students
FROM teacher_profiles tp JOIN public_classes pc ON pc.teacher_slug = tp.slug
GROUP BY tp.slug, tp.display_name, tp.headline, tp.bio, tp.photo_url, tp.highlights
""",
    """
CREATE VIEW public_institutes AS
SELECT t.slug, t.name, t.logo_url, count(pc.id) AS class_count,
       array_agg(DISTINCT pc.subject_name) AS subject_names,
       count(DISTINCT pc.teacher_slug) AS teacher_count
FROM tenants t JOIN public_classes pc ON pc.tenant_id = t.id
WHERE t.org_type = 'institute'
GROUP BY t.slug, t.name, t.logo_url
""",
    """
CREATE VIEW public_subjects AS
SELECT s.id, s.slug, s.name, s.sort_order,
       (SELECT count(*) FROM public_classes pc WHERE pc.subject_id = s.id) AS class_count,
       (SELECT count(DISTINCT pc.teacher_slug) FROM public_classes pc WHERE pc.subject_id = s.id) AS teacher_count
FROM subjects s WHERE s.is_active
""",
)
_VIEW_NAMES = ("public_classes", "public_class_months", "public_lessons", "public_teachers",
               "public_institutes", "public_subjects")


def upgrade() -> None:
    reserved = ",".join(f"'{r}'" for r in RESERVED)
    op.execute(f"""
        CREATE FUNCTION is_reserved_slug(p_slug text) RETURNS boolean
        LANGUAGE sql IMMUTABLE AS $$ SELECT p_slug = ANY (ARRAY[{reserved}]) $$
    """)

    op.execute("""
        CREATE TABLE subjects (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            slug        text NOT NULL UNIQUE
                        CHECK (slug ~ '^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])$' AND NOT is_reserved_slug(slug)),
            name        text NOT NULL,
            sort_order  integer NOT NULL DEFAULT 0,
            is_active   boolean NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now()
        )
    """)
    values = ",".join(f"('{slug}', '{name}', {order})" for slug, name, order in SUBJECTS)
    op.execute(f"INSERT INTO subjects (slug, name, sort_order) VALUES {values}")

    op.execute("ALTER TABLE classes ADD COLUMN subject_id uuid REFERENCES subjects(id)")
    op.execute("CREATE INDEX idx_classes_subject ON classes (subject_id) WHERE status = 'published'")
    op.execute("""
        UPDATE classes c SET subject_id = s.id FROM subjects s
        WHERE c.subject_id IS NULL AND (lower(trim(c.subject)) = lower(s.name) OR lower(trim(c.subject)) = s.slug
              OR (lower(trim(c.subject)) IN ('maths', 'math') AND s.slug = 'mathematics'))
    """)

    op.execute("ALTER TABLE tenants ADD COLUMN is_listed boolean NOT NULL DEFAULT true")

    op.execute("""
        CREATE TABLE teacher_profiles (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
            slug         text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$'),
            display_name text NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 80),
            headline     text CHECK (char_length(headline) <= 120),
            bio          text CHECK (char_length(bio) <= 2000),
            photo_url    text,
            highlights   text[] NOT NULL DEFAULT '{}' CHECK (cardinality(highlights) <= 6),
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("""
        CREATE TRIGGER trg_teacher_profiles_updated BEFORE UPDATE ON teacher_profiles
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)
    # Everyone who teaches a class gets a profile; the slug comes from their name (Latin letters
    # only), else 'teacher-<6 hex>', with -2, -3… on clashes.
    op.execute("""
        WITH teachers AS (
            SELECT DISTINCT ON (u.id) u.id AS user_id, COALESCE(NULLIF(tm.display_name, ''), u.full_name) AS name
            FROM classes c
            JOIN tenant_members tm ON tm.tenant_id = c.tenant_id AND tm.id = c.teacher_member_id
            JOIN users u ON u.id = tm.user_id
            ORDER BY u.id
        ), slugged AS (
            SELECT user_id, left(name, 80) AS name,
                   COALESCE(NULLIF(left(trim(BOTH '-' FROM regexp_replace(lower(name), '[^a-z0-9]+', '-', 'g')), 34), ''),
                            'teacher-' || left(md5(user_id::text), 6)) AS base
            FROM teachers
        ), numbered AS (
            SELECT user_id, name, base, row_number() OVER (PARTITION BY base ORDER BY user_id) AS n FROM slugged
        )
        INSERT INTO teacher_profiles (user_id, slug, display_name)
        SELECT user_id,
               CASE WHEN length(base) < 3 THEN 'teacher-' || left(md5(user_id::text), 6)
                    WHEN n = 1 THEN base ELSE base || '-' || n END,
               name
        FROM numbered
    """)

    for view in _PUBLIC_VIEWS:
        op.execute(view)
    for name in _VIEW_NAMES:
        # Owned by eduzone_admin (BYPASSRLS): the views read across tenants, but only these columns.
        op.execute(f"ALTER VIEW {name} OWNER TO eduzone_admin")
        op.execute(f"REVOKE ALL ON {name} FROM PUBLIC")
        op.execute(f"GRANT SELECT ON {name} TO eduzone_app")

    op.execute("GRANT SELECT ON subjects TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON teacher_profiles TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON subjects, teacher_profiles TO eduzone_admin")


def downgrade() -> None:
    for name in reversed(_VIEW_NAMES):
        op.execute(f"DROP VIEW {name}")
    op.execute("DROP TABLE teacher_profiles")
    op.execute("ALTER TABLE tenants DROP COLUMN is_listed")
    op.execute("ALTER TABLE classes DROP COLUMN subject_id")
    op.execute("DROP TABLE subjects")
    op.execute("DROP FUNCTION is_reserved_slug(text)")
