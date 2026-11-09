"""Courses, step C3 (docs/COURSES.md section C.4): lecture completion for course progress.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-09

- lesson_completions: one row per (student, lecture). Video lectures complete automatically when the video passes
  90% (`auto`, from lesson_progress); articles and PDFs by "Mark as complete" (`manual`). A student may un-mark
  (delete their row), so DELETE is granted. Course progress = completed published lectures / published lectures.
- Tenant-scoped like every business table (forced RLS, tenant_isolation), plus the SELECT-only user policy of
  migration 0006 so "My learning" can read a student's own rows across tenants.
- class_kinds(ids): the kind (tuition | course) of classes, for receipts read in a user transaction.
"""

from alembic import op

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE lesson_completions (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           uuid NOT NULL DEFAULT current_tenant_id(),
            student_member_id   uuid NOT NULL,
            lesson_id           uuid NOT NULL,
            source              text NOT NULL CHECK (source IN ('auto','manual')),
            completed_at        timestamptz NOT NULL DEFAULT now(),
            UNIQUE (student_member_id, lesson_id),
            FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id),
            FOREIGN KEY (tenant_id, lesson_id) REFERENCES lessons (tenant_id, id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX idx_lesson_completions_member ON lesson_completions (tenant_id, student_member_id)")
    op.execute("ALTER TABLE lesson_completions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE lesson_completions FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON lesson_completions
                  USING (tenant_id = current_tenant_id()) WITH CHECK (tenant_id = current_tenant_id())""")
    op.execute("""CREATE POLICY user_own_rows ON lesson_completions FOR SELECT
                  USING (student_member_id IN (SELECT id FROM tenant_members WHERE user_id = current_user_id()))""")
    op.execute("GRANT SELECT, INSERT, DELETE ON lesson_completions TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON lesson_completions TO eduzone_admin")

    # Receipts across tenants link a course to the course player and a class to its page; the user transaction
    # can't read classes, so this returns only the kind of the ids asked for.
    op.execute("""
        CREATE FUNCTION class_kinds(p_ids uuid[]) RETURNS TABLE (id uuid, kind text)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
            SELECT c.id, c.kind FROM classes c WHERE c.id = ANY (p_ids)
        $$
    """)
    op.execute("ALTER FUNCTION class_kinds(uuid[]) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION class_kinds(uuid[]) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION class_kinds(uuid[]) TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS class_kinds(uuid[])")
    op.execute("DROP TABLE lesson_completions")
