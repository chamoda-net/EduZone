"""Public free previews of tuition lessons.

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-26

- public_lessons.video_seconds: the length of a published lesson's ready videos (0 when it has none), like
  public_course_lectures.video_seconds. The class page offers a free-preview lesson with a video to anyone,
  without signing in (POST /market/lessons/{id}/preview). Still never Zoom links, descriptions or files.
"""

from alembic import op

revision: str = "0021"
down_revision: str | None = "0020"
branch_labels: str | None = None
depends_on: str | None = None

_OLD = """
CREATE OR REPLACE VIEW public_lessons AS
SELECT l.id, l.class_id, l.class_month_id, l.title, l.lesson_type, l.sort_order, l.scheduled_at,
       l.duration_minutes, l.is_free_preview
FROM lessons l JOIN public_classes pc ON pc.id = l.class_id
WHERE l.is_published
"""

_NEW = """
CREATE OR REPLACE VIEW public_lessons AS
SELECT l.id, l.class_id, l.class_month_id, l.title, l.lesson_type, l.sort_order, l.scheduled_at,
       l.duration_minutes, l.is_free_preview,
       COALESCE((SELECT sum(a.duration_seconds) FROM lesson_resources r
                 JOIN media_assets a ON a.id = r.media_asset_id AND a.kind = 'video' AND a.status = 'ready'
                 WHERE r.lesson_id = l.id), 0)::int AS video_seconds
FROM lessons l JOIN public_classes pc ON pc.id = l.class_id
WHERE l.is_published
"""


def upgrade() -> None:
    op.execute(_NEW)


def downgrade() -> None:
    # A view can't drop a column with CREATE OR REPLACE.
    op.execute("DROP VIEW public_lessons")
    op.execute(_OLD.replace("CREATE OR REPLACE VIEW", "CREATE VIEW"))
    op.execute("ALTER VIEW public_lessons OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON public_lessons FROM PUBLIC")
    op.execute("GRANT SELECT ON public_lessons TO eduzone_app")
