"""Courses, step C4 (docs/COURSES.md sections C.5 and C.6): reviews and certificates.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-09

- course_reviews: one review per student per course (1-5 stars, a comment, the instructor's reply); staff can hide
  one with a reason. classes.rating_avg / rating_count are recomputed from visible reviews in the same transaction.
- certificates: issued at 100% of a paid course; snapshots of the names, title and length at issue time; a random,
  non-sequential number (EZCERT-XXXX-XXXX); revoked later by a refund (step C6).
- Both tenant-scoped (forced RLS, tenant_isolation) with the user SELECT policy so a student reads their own rows
  across tenants.
- public_course_reviews: visible reviews of public courses with the reviewer's first name and initial only.
- verify_certificate(no): the public verify page's only read: snapshot fields and status, nothing else.
"""

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | None = None
depends_on: str | None = None

_OWN = "student_member_id IN (SELECT id FROM tenant_members WHERE user_id = current_user_id())"


def _tenant_table(name: str) -> None:
    op.execute(f"ALTER TABLE {name} ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {name} FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY tenant_isolation ON {name}
                   USING (tenant_id = current_tenant_id()) WITH CHECK (tenant_id = current_tenant_id())""")
    op.execute(f"CREATE POLICY user_own_rows ON {name} FOR SELECT USING ({_OWN})")


def upgrade() -> None:
    op.execute("""
        CREATE TABLE course_reviews (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           uuid NOT NULL DEFAULT current_tenant_id(),
            class_id            uuid NOT NULL,
            student_member_id   uuid NOT NULL,
            rating              smallint NOT NULL CHECK (rating BETWEEN 1 AND 5),
            comment             text CHECK (char_length(comment) <= 2000),
            status              text NOT NULL DEFAULT 'visible' CHECK (status IN ('visible','hidden')),
            hidden_reason       text CHECK (char_length(hidden_reason) <= 500),
            instructor_reply    text CHECK (char_length(instructor_reply) <= 2000),
            replied_at          timestamptz,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now(),
            UNIQUE (class_id, student_member_id),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id)
        )
    """)
    op.execute("CREATE INDEX idx_course_reviews_class ON course_reviews (tenant_id, class_id, created_at DESC)")
    _tenant_table("course_reviews")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON course_reviews TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON course_reviews TO eduzone_admin")

    op.execute("""
        CREATE TABLE certificates (
            id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id               uuid NOT NULL DEFAULT current_tenant_id(),
            class_id                uuid NOT NULL,
            student_member_id       uuid NOT NULL,
            certificate_no          text NOT NULL UNIQUE CHECK (certificate_no ~ '^EZCERT-[A-Z0-9]{4}-[A-Z0-9]{4}$'),
            student_name            text NOT NULL,
            course_title            text NOT NULL,
            instructor_name         text NOT NULL,
            total_video_seconds     integer NOT NULL,
            issued_at               timestamptz NOT NULL DEFAULT now(),
            revoked_at              timestamptz,
            revoke_reason           text,
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id),
            FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id)
        )
    """)
    op.execute("CREATE UNIQUE INDEX uq_certificate_active ON certificates (class_id, student_member_id) "
               "WHERE revoked_at IS NULL")
    _tenant_table("certificates")
    op.execute("GRANT SELECT, INSERT, UPDATE ON certificates TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON certificates TO eduzone_admin")

    op.execute("""
        CREATE VIEW public_course_reviews AS
        SELECT r.id, r.class_id AS course_id, r.rating, r.comment, r.instructor_reply, r.replied_at, r.created_at,
               r.updated_at,
               CASE WHEN array_length(n.w, 1) > 1 THEN n.w[1] || ' ' || upper(left(n.w[array_length(n.w, 1)], 1)) || '.'
                    ELSE n.w[1] END AS reviewer
        FROM course_reviews r
        JOIN public_courses pc ON pc.id = r.class_id
        JOIN tenant_members tm ON tm.id = r.student_member_id
        JOIN users u ON u.id = tm.user_id
        CROSS JOIN LATERAL (SELECT regexp_split_to_array(btrim(u.full_name), '[[:space:]]+') AS w) n
        WHERE r.status = 'visible'
    """)
    op.execute("ALTER VIEW public_course_reviews OWNER TO eduzone_admin")
    op.execute("GRANT SELECT ON public_course_reviews TO eduzone_app")

    op.execute("""
        CREATE FUNCTION verify_certificate(p_no text)
        RETURNS TABLE (certificate_no text, student_name text, course_title text, instructor_name text,
                       org_name text, total_video_seconds integer, issued_at timestamptz, revoked_at timestamptz)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
            SELECT c.certificate_no, c.student_name, c.course_title, c.instructor_name, t.name, c.total_video_seconds,
                   c.issued_at, c.revoked_at
            FROM certificates c JOIN tenants t ON t.id = c.tenant_id
            WHERE c.certificate_no = upper(p_no)
        $$
    """)
    op.execute("ALTER FUNCTION verify_certificate(text) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION verify_certificate(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION verify_certificate(text) TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION verify_certificate(text)")
    op.execute("DROP VIEW public_course_reviews")
    op.execute("DROP TABLE certificates")
    op.execute("DROP TABLE course_reviews")
