"""Seats and registration for tuition classes, step S1 (docs/SEATS.md).

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-24

- classes: seat_limit (NULL = no limit), show_seat_count, registration for new students (open, ask, closed) and an
  optional start date after which registration switches by itself. Courses keep the defaults (check constraint).
- orders.seat_held_until: a pending order holds a seat until then, so a failed or cancelled payment frees it at once
  and nothing has to expire it.
- access_grants.takes_seat: false for a past month bought late (or given after the month closed), which takes no seat
  and doesn't make someone a returning student.
"""

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE classes
            ADD COLUMN seat_limit      integer CHECK (seat_limit BETWEEN 1 AND 10000),
            ADD COLUMN show_seat_count boolean NOT NULL DEFAULT true,
            ADD COLUMN registration    text NOT NULL DEFAULT 'open' CHECK (registration IN ('open','ask','closed')),
            ADD COLUMN starts_on       date,
            ADD COLUMN registration_after_start text CHECK (registration_after_start IN ('open','ask','closed')),
            ADD CONSTRAINT classes_seats_tuition_only CHECK (
                kind = 'tuition' OR (seat_limit IS NULL AND show_seat_count AND registration = 'open'
                                     AND starts_on IS NULL AND registration_after_start IS NULL)),
            ADD CONSTRAINT classes_after_start_needs_date CHECK (
                registration_after_start IS NULL OR starts_on IS NOT NULL)
    """)
    op.execute("ALTER TABLE orders ADD COLUMN seat_held_until timestamptz")
    # Who is paying for a seat of this class now: found through the items.
    op.execute("CREATE INDEX idx_order_items_class ON order_items (tenant_id, class_id, class_month_id)")

    op.execute("ALTER TABLE access_grants ADD COLUMN takes_seat boolean NOT NULL DEFAULT true")
    op.execute("""
        UPDATE access_grants g SET takes_seat = false FROM order_items i
        WHERE i.id = g.order_item_id AND i.late_request_id IS NOT NULL
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE access_grants DROP COLUMN takes_seat")
    op.execute("DROP INDEX idx_order_items_class")
    op.execute("ALTER TABLE orders DROP COLUMN seat_held_until")
    op.execute("""
        ALTER TABLE classes
            DROP CONSTRAINT classes_after_start_needs_date, DROP CONSTRAINT classes_seats_tuition_only,
            DROP COLUMN registration_after_start, DROP COLUMN starts_on, DROP COLUMN registration,
            DROP COLUMN show_seat_count, DROP COLUMN seat_limit
    """)
