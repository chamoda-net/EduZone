"""Seats, step S2 (docs/SEATS.md): returning students keep their seat until a renewal date.

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-24

- classes.renewal_day: the day of the month until which returning students' seats are kept (7 by default).
- class_months.opened_at / renew_until: set when the month opens (existing open and closed months: from created_at).
- seat_keeps: the staff's decision about one student's kept seat in one month (keep until, or release).
"""

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | None = None
depends_on: str | None = None

_OTHER = ("(seat_limit IS NULL AND show_seat_count AND registration = 'open' AND starts_on IS NULL "
          "AND registration_after_start IS NULL{extra})")


def _seats_tuition_only(extra: str) -> None:
    op.execute("ALTER TABLE classes DROP CONSTRAINT classes_seats_tuition_only")
    op.execute("ALTER TABLE classes ADD CONSTRAINT classes_seats_tuition_only CHECK (kind = 'tuition' OR "
               + _OTHER.format(extra=extra) + ")")


def upgrade() -> None:
    op.execute("ALTER TABLE classes ADD COLUMN renewal_day smallint NOT NULL DEFAULT 7 "
               "CHECK (renewal_day BETWEEN 1 AND 28)")
    _seats_tuition_only(" AND renewal_day = 7")
    op.execute("ALTER TABLE class_months ADD COLUMN opened_at timestamptz, ADD COLUMN renew_until timestamptz")
    # The end of the 7th, Sri Lanka time, and at least 3 days after opening.
    op.execute("""
        UPDATE class_months SET opened_at = created_at,
               renew_until = greatest((month_start + 7)::timestamp AT TIME ZONE 'Asia/Colombo',
                                      created_at + interval '3 days')
        WHERE status <> 'upcoming'
    """)
    op.execute("""
        CREATE TABLE seat_keeps (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            class_id          uuid NOT NULL,
            class_month_id    uuid NOT NULL,
            student_member_id uuid NOT NULL,
            action            text NOT NULL CHECK (action IN ('keep','release')),
            keep_until        timestamptz,
            decided_by        uuid NOT NULL,
            decided_at        timestamptz NOT NULL DEFAULT now(),
            UNIQUE (class_month_id, student_member_id),
            UNIQUE (tenant_id, id),
            CHECK ((action = 'keep') = (keep_until IS NOT NULL)),
            FOREIGN KEY (tenant_id, class_id, class_month_id)
                REFERENCES class_months (tenant_id, class_id, id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id),
            FOREIGN KEY (tenant_id, decided_by) REFERENCES tenant_members (tenant_id, id)
        )
    """)
    op.execute("ALTER TABLE seat_keeps ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE seat_keeps FORCE ROW LEVEL SECURITY")
    op.execute("CREATE POLICY tenant_isolation ON seat_keeps USING (tenant_id = current_tenant_id()) "
               "WITH CHECK (tenant_id = current_tenant_id())")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON seat_keeps TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP TABLE seat_keeps")
    op.execute("ALTER TABLE class_months DROP COLUMN renew_until, DROP COLUMN opened_at")
    _seats_tuition_only("")
    op.execute("ALTER TABLE classes DROP COLUMN renewal_day")
