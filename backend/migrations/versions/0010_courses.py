"""Courses, step C1 (docs/COURSES.md sections C.1–C.3).

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-02

- course_categories: EduZone-managed, two levels, readable by the app role (public catalogue data).
- A course is a `classes` row with kind = 'course': one-time or free, no exam or batch year, a platform-wide slug
  (/course/<slug>), landing-page and intended-learner fields, and a staff review on its first publish
  (status 'in_review'). Tuition classes never enter in_review (service rule).
- course_sections and lessons.section_id: course lectures live in sections, never in months; a new
  lesson_type 'article' carries Markdown in lessons.article_body.
- course_slug_taken(): course slugs are unique across tenants, which the app role can't see (SECURITY DEFINER).
- The public tuition views show tuition classes only (courses get their own catalogue in step C2).
- Reserved slugs gain the course routes (course, courses, instructor, certificates, wishlist, categories) and
  the existing /checkouts page.
- teacher_applications.offers: what the applicant wants to sell (classes, courses or both).
"""

import importlib.util
from pathlib import Path

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | None = None
depends_on: str | None = None


def _m0007():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("m0007", Path(__file__).with_name("0007_marketplace.py"))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


NEW_RESERVED = ("course", "courses", "instructor", "certificates", "wishlist", "categories", "checkouts")

CATEGORIES = (
    ("it-networking", "IT & Networking", 10), ("software-development", "Software Development", 20),
    ("business", "Business", 30), ("finance-accounting", "Finance & Accounting", 40), ("design", "Design", 50),
    ("marketing", "Marketing", 60), ("languages", "Languages", 70), ("personal-development", "Personal Development", 80),
    ("exam-skills", "Exam Skills", 90), ("music", "Music", 100), ("health-fitness", "Health & Fitness", 110),
)


def _reserved_function(words: tuple[str, ...]) -> str:
    listed = ",".join(f"'{r}'" for r in words)
    return f"""
        CREATE OR REPLACE FUNCTION is_reserved_slug(p_slug text) RETURNS boolean
        LANGUAGE sql IMMUTABLE AS $$ SELECT p_slug = ANY (ARRAY[{listed}]) $$
    """


def upgrade() -> None:
    m0007 = _m0007()

    # --- reserved routes (no subject or teacher profile may already use them) ----------------
    op.execute(f"""
        DO $$ BEGIN
            IF EXISTS (SELECT 1 FROM subjects WHERE slug = ANY (ARRAY[{",".join(f"'{r}'" for r in NEW_RESERVED)}]))
               OR EXISTS (SELECT 1 FROM teacher_profiles
                          WHERE slug = ANY (ARRAY[{",".join(f"'{r}'" for r in NEW_RESERVED)}])) THEN
                RAISE EXCEPTION 'a subject or teacher profile already uses a newly reserved slug';
            END IF;
        END $$
    """)
    op.execute(_reserved_function(tuple(m0007.RESERVED) + NEW_RESERVED))

    # --- C.1 categories ---------------------------------------------------------------------
    op.execute("""
        CREATE TABLE course_categories (
            id          smallint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            parent_id   smallint REFERENCES course_categories(id),
            slug        text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])$'),
            name_en     text NOT NULL CHECK (char_length(name_en) BETWEEN 2 AND 60),
            name_si     text CHECK (char_length(name_si) <= 60),
            name_ta     text CHECK (char_length(name_ta) <= 60),
            sort_order  integer NOT NULL DEFAULT 0,
            is_active   boolean NOT NULL DEFAULT true,
            created_at  timestamptz NOT NULL DEFAULT now(),
            CHECK (parent_id IS NULL OR parent_id <> id)
        )
    """)
    values = ",".join(f"('{s}', '{n.replace(chr(39), chr(39) * 2)}', {o})" for s, n, o in CATEGORIES)
    op.execute(f"INSERT INTO course_categories (slug, name_en, sort_order) VALUES {values}")
    op.execute("GRANT SELECT ON course_categories TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON course_categories TO eduzone_admin")

    # --- C.2 courses are classes with kind = 'course' ----------------------------------------
    op.execute("""
        ALTER TABLE classes
            ADD COLUMN kind                text NOT NULL DEFAULT 'tuition' CHECK (kind IN ('tuition','course')),
            ADD COLUMN subtitle            text CHECK (char_length(subtitle) <= 120),
            ADD COLUMN category_id         smallint REFERENCES course_categories(id),
            ADD COLUMN level               text CHECK (level IN ('beginner','intermediate','advanced','all')),
            ADD COLUMN learning_objectives text[] NOT NULL DEFAULT '{}',
            ADD COLUMN requirements        text[] NOT NULL DEFAULT '{}',
            ADD COLUMN target_audience     text[] NOT NULL DEFAULT '{}',
            ADD COLUMN promo_media_id      uuid,
            ADD COLUMN welcome_message     text CHECK (char_length(welcome_message) <= 1000),
            ADD COLUMN completion_message  text CHECK (char_length(completion_message) <= 1000),
            ADD COLUMN total_video_seconds integer NOT NULL DEFAULT 0,
            ADD COLUMN lecture_count       integer NOT NULL DEFAULT 0,
            ADD COLUMN rating_avg          numeric(3,2),
            ADD COLUMN rating_count        integer NOT NULL DEFAULT 0,
            ADD COLUMN review_note         text CHECK (char_length(review_note) <= 2000),
            ADD COLUMN submitted_at        timestamptz,
            ADD COLUMN first_published_at  timestamptz,
            ADD CONSTRAINT classes_promo_media_fk FOREIGN KEY (tenant_id, promo_media_id)
                REFERENCES media_assets (tenant_id, id),
            ADD CONSTRAINT classes_course_pricing CHECK (kind <> 'course' OR pricing_model IN ('one_time','free')),
            ADD CONSTRAINT classes_course_no_exam CHECK (kind <> 'course' OR (exam IS NULL AND batch_year IS NULL))
    """)
    op.execute("ALTER TABLE classes DROP CONSTRAINT classes_status_check")
    op.execute("""ALTER TABLE classes ADD CONSTRAINT classes_status_check
                  CHECK (status IN ('draft','in_review','published','archived'))""")
    op.execute("ALTER TABLE classes ADD CONSTRAINT classes_review_course_only CHECK (status <> 'in_review' OR kind = 'course')")
    op.execute("CREATE UNIQUE INDEX uq_course_slug ON classes (slug) WHERE kind = 'course'")
    op.execute("CREATE INDEX idx_classes_courses ON classes (category_id, status) WHERE kind = 'course'")
    op.execute("CREATE INDEX idx_classes_in_review ON classes (submitted_at) WHERE status = 'in_review'")

    op.execute("""
        CREATE FUNCTION course_slug_taken(p_slug text, p_exclude uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
            SELECT EXISTS (SELECT 1 FROM classes
                           WHERE kind = 'course' AND slug = p_slug AND id IS DISTINCT FROM p_exclude)
        $$
    """)
    op.execute("ALTER FUNCTION course_slug_taken(text, uuid) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION course_slug_taken(text, uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION course_slug_taken(text, uuid) TO eduzone_app")

    # --- C.3 sections and article lectures --------------------------------------------------
    op.execute("""
        CREATE TABLE course_sections (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id   uuid NOT NULL DEFAULT current_tenant_id(),
            class_id    uuid NOT NULL,
            title       text NOT NULL CHECK (char_length(title) BETWEEN 1 AND 200),
            sort_order  integer NOT NULL DEFAULT 0,
            created_at  timestamptz NOT NULL DEFAULT now(),
            updated_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX idx_sections_class ON course_sections (tenant_id, class_id, sort_order)")
    op.execute("ALTER TABLE course_sections ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE course_sections FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON course_sections
                  USING (tenant_id = current_tenant_id()) WITH CHECK (tenant_id = current_tenant_id())""")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON course_sections TO eduzone_app, eduzone_admin")

    op.execute("""
        ALTER TABLE lessons
            ADD COLUMN section_id   uuid,
            ADD COLUMN article_body text CHECK (char_length(article_body) <= 50000),
            ADD CONSTRAINT lessons_section_fk FOREIGN KEY (tenant_id, section_id)
                REFERENCES course_sections (tenant_id, id) ON DELETE CASCADE,
            ADD CONSTRAINT lessons_section_or_month CHECK (section_id IS NULL OR class_month_id IS NULL)
    """)
    op.execute("ALTER TABLE lessons DROP CONSTRAINT lessons_lesson_type_check")
    op.execute("""ALTER TABLE lessons ADD CONSTRAINT lessons_lesson_type_check
                  CHECK (lesson_type IN ('live','recorded','document','article'))""")
    op.execute("""ALTER TABLE lessons ADD CONSTRAINT lessons_article_body
                  CHECK (lesson_type <> 'article' OR article_body IS NOT NULL)""")
    op.execute("CREATE INDEX idx_lessons_section ON lessons (tenant_id, section_id, sort_order) WHERE section_id IS NOT NULL")

    # --- the tuition catalogue shows tuition only ---------------------------------------------
    op.execute(m0007._PUBLIC_CLASSES
               .replace("CREATE VIEW public_classes", "CREATE OR REPLACE VIEW public_classes")
               .replace("WHERE c.status = 'published'", "WHERE c.status = 'published' AND c.kind = 'tuition'"))

    # --- what an applicant wants to sell ------------------------------------------------------
    op.execute("""ALTER TABLE teacher_applications ADD COLUMN offers text NOT NULL DEFAULT 'classes'
                  CHECK (offers IN ('classes','courses','both'))""")


def downgrade() -> None:
    m0007 = _m0007()
    op.execute("ALTER TABLE teacher_applications DROP COLUMN offers")
    op.execute(m0007._PUBLIC_CLASSES.replace("CREATE VIEW public_classes", "CREATE OR REPLACE VIEW public_classes"))
    op.execute("DELETE FROM lessons WHERE section_id IS NOT NULL OR lesson_type = 'article'")
    op.execute("ALTER TABLE lessons DROP CONSTRAINT lessons_article_body")
    op.execute("ALTER TABLE lessons DROP CONSTRAINT lessons_lesson_type_check")
    op.execute("""ALTER TABLE lessons ADD CONSTRAINT lessons_lesson_type_check
                  CHECK (lesson_type IN ('live','recorded','document'))""")
    op.execute("ALTER TABLE lessons DROP CONSTRAINT lessons_section_or_month, DROP CONSTRAINT lessons_section_fk, "
               "DROP COLUMN section_id, DROP COLUMN article_body")
    op.execute("DROP TABLE course_sections")
    op.execute("DROP FUNCTION course_slug_taken(text, uuid)")
    op.execute("DELETE FROM classes WHERE kind = 'course'")
    op.execute("ALTER TABLE classes DROP CONSTRAINT classes_review_course_only, DROP CONSTRAINT classes_status_check")
    op.execute("""ALTER TABLE classes ADD CONSTRAINT classes_status_check
                  CHECK (status IN ('draft','published','archived'))""")
    op.execute("""
        ALTER TABLE classes
            DROP CONSTRAINT classes_course_no_exam, DROP CONSTRAINT classes_course_pricing,
            DROP CONSTRAINT classes_promo_media_fk,
            DROP COLUMN kind, DROP COLUMN subtitle, DROP COLUMN category_id, DROP COLUMN level,
            DROP COLUMN learning_objectives, DROP COLUMN requirements, DROP COLUMN target_audience,
            DROP COLUMN promo_media_id, DROP COLUMN welcome_message, DROP COLUMN completion_message,
            DROP COLUMN total_video_seconds, DROP COLUMN lecture_count, DROP COLUMN rating_avg,
            DROP COLUMN rating_count, DROP COLUMN review_note, DROP COLUMN submitted_at,
            DROP COLUMN first_published_at
    """)
    op.execute("DROP TABLE course_categories")
    op.execute(_reserved_function(tuple(m0007.RESERVED)))
