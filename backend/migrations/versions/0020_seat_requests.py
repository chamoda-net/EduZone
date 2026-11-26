"""Seats, step S3 (docs/SEATS.md): seat requests, the notify list and the public seat information.

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-24

- seat_requests: a student asks for a seat (registration = ask), the teacher accepts (the seat is held until
  held_until) or refuses. One row per student, class and month. seat_waits: the notify list, one row per student and
  class. Both: tenant RLS, plus SELECT of the student's own rows (user policy).
- seat_last_month(), seat_holders() (SECURITY INVOKER, so RLS applies): the one place that counts seats, used by
  app/modules/seats and by the public view. seat_registration(): registration today.
- public_seats: per public class (each open month of a monthly one) whether it is full and registration; the numbers
  only when the teacher shows them. public_seats_taken() (SECURITY DEFINER) gives the view the count.
- public_classes.students: a class with limited seats shows the seats taken (0 when hidden), not who joined.
"""

import importlib.util
from pathlib import Path

from alembic import op

revision: str = "0020"
down_revision: str | None = "0019"
branch_labels: str | None = None
depends_on: str | None = None

_SEAT_LAST_MONTH = """
CREATE FUNCTION seat_last_month(p_class uuid, p_month uuid)
RETURNS TABLE (student_member_id uuid, granted_at timestamptz, stayed boolean, before_opening boolean,
               action text, kept_until timestamptz, is_open boolean)
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    -- The students of the class's previous month (the latest earlier one that isn't upcoming) with a seat there, and
    -- the staff's decision about them in this month. stayed: in the class ever since they got that seat (leaving gives
    -- it up, rejoining doesn't bring it back). before_opening: they had it before this month opened.
    SELECT g.student_member_id, g.granted_at, e.enrolled_at <= g.granted_at,
           g.granted_at < COALESCE(m.opened_at, m.created_at), k.action, COALESCE(k.keep_until, m.renew_until),
           m.status = 'open'
    FROM class_months m
    JOIN LATERAL (SELECT p.id FROM class_months p
                  WHERE p.class_id = m.class_id AND p.month_start < m.month_start AND p.status <> 'upcoming'
                  ORDER BY p.month_start DESC LIMIT 1) prev ON true
    JOIN access_grants g ON g.class_month_id = prev.id AND g.takes_seat AND g.revoked_at IS NULL
    JOIN class_enrollments e ON e.class_id = m.class_id AND e.student_member_id = g.student_member_id
                            AND e.status = 'active'
    JOIN tenant_members tm ON tm.id = g.student_member_id AND tm.status = 'active'
    LEFT JOIN seat_keeps k ON k.class_month_id = m.id AND k.student_member_id = g.student_member_id
    WHERE m.id = p_month AND m.class_id = p_class
$$
"""

_SEAT_HOLDERS = """
CREATE FUNCTION seat_holders(p_class uuid, p_month uuid)
RETURNS TABLE (student_member_id uuid, kind text, source text, since timestamptz, held_until timestamptz)
LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
    -- Everyone with a seat of the class (of that month, or NULL): one row per reason, so a student may appear twice.
    SELECT g.student_member_id, 'access', g.source, g.granted_at, NULL::timestamptz
    FROM access_grants g
    WHERE g.class_id = p_class AND g.class_month_id IS NOT DISTINCT FROM p_month AND g.takes_seat
      AND g.revoked_at IS NULL AND (g.expires_at IS NULL OR g.expires_at > now())
      AND (g.source <> 'free' OR EXISTS (
          SELECT 1 FROM class_enrollments e
          WHERE e.class_id = g.class_id AND e.student_member_id = g.student_member_id AND e.status = 'active'))
    UNION ALL
    SELECT o.student_member_id, 'paying', NULL, o.created_at, o.seat_held_until
    FROM orders o JOIN order_items i ON i.order_id = o.id
    WHERE i.class_id = p_class AND i.class_month_id IS NOT DISTINCT FROM p_month
      AND o.status = 'pending' AND o.seat_held_until > now()
    UNION ALL
    SELECT r.student_member_id, 'accepted', NULL, r.decided_at, r.held_until
    FROM seat_requests r
    WHERE r.class_id = p_class AND r.class_month_id IS NOT DISTINCT FROM p_month
      AND r.status = 'approved' AND r.held_until > now()
    UNION ALL
    SELECT l.student_member_id, 'kept', NULL, l.granted_at, l.kept_until
    FROM seat_last_month(p_class, p_month) l
    WHERE l.is_open AND l.action IS DISTINCT FROM 'release' AND l.kept_until > now()
      AND (l.action = 'keep' OR (l.before_opening AND l.stayed))
$$
"""

_PUBLIC_SEATS_TAKEN = """
CREATE FUNCTION public_seats_taken(p_class uuid, p_month uuid) RETURNS bigint
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT count(DISTINCT h.student_member_id)
    FROM classes c
    JOIN tenants t ON t.id = c.tenant_id AND t.status = 'active' AND t.is_listed
    CROSS JOIN LATERAL seat_holders(c.id, p_month) h
    WHERE c.id = p_class AND c.kind = 'tuition' AND c.status = 'published' AND c.seat_limit IS NOT NULL
$$
"""

_PUBLIC_SEATS = """
CREATE VIEW public_seats AS
SELECT x.class_id, x.class_month_id, x.registration,
       CASE WHEN x.show_seat_count THEN x.seat_limit END AS seat_limit,
       CASE WHEN x.show_seat_count AND x.seat_limit IS NOT NULL THEN greatest(0, x.seat_limit - x.taken) END
           AS seats_left,
       COALESCE(x.taken >= x.seat_limit, false) AS is_full
FROM (
    SELECT pc.id AS class_id, m.id AS class_month_id, c.seat_limit, c.show_seat_count,
           seat_registration(c.registration, c.registration_after_start, c.starts_on) AS registration,
           CASE WHEN c.seat_limit IS NOT NULL THEN public_seats_taken(c.id, m.id) END AS taken
    FROM public_classes pc
    JOIN classes c ON c.id = pc.id
    LEFT JOIN class_months m ON m.class_id = c.id AND m.status = 'open' AND c.pricing_model = 'monthly'
    WHERE c.pricing_model <> 'monthly' OR m.id IS NOT NULL
) x
"""

_JOINED = "(SELECT count(*) FROM class_enrollments e WHERE e.class_id = c.id AND e.status = 'active') AS students"
_SEATED = ("CASE WHEN c.seat_limit IS NULL THEN (SELECT count(*) FROM class_enrollments e WHERE e.class_id = c.id "
           "AND e.status = 'active') WHEN c.show_seat_count THEN public_seats_taken(c.id, om.id) ELSE 0::bigint "
           "END AS students")


def _public_classes(students: str) -> str:
    """public_classes as 0010 left it (tuition only), with how `students` is counted."""
    spec = importlib.util.spec_from_file_location("m0007", Path(__file__).with_name("0007_marketplace.py"))
    assert spec is not None and spec.loader is not None
    m0007 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m0007)
    sql: str = m0007._PUBLIC_CLASSES
    for old, new in (("CREATE VIEW public_classes", "CREATE OR REPLACE VIEW public_classes"),
                     ("WHERE c.status = 'published'", "WHERE c.status = 'published' AND c.kind = 'tuition'"),
                     (_JOINED, students)):
        assert sql.count(old) == 1, old
        sql = sql.replace(old, new)
    return sql


_USER_POLICY = """
    CREATE POLICY user_own_rows ON {table} FOR SELECT USING (
        student_member_id IN (SELECT id FROM tenant_members WHERE user_id = current_user_id()))
"""


def upgrade() -> None:
    op.execute("""
        CREATE TABLE seat_requests (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            class_id          uuid NOT NULL,
            class_month_id    uuid,
            student_member_id uuid NOT NULL,
            status            text NOT NULL DEFAULT 'pending'
                              CHECK (status IN ('pending','approved','rejected','withdrawn','used')),
            student_note      text CHECK (char_length(student_note) <= 500),
            decided_by        uuid,
            decided_at        timestamptz,
            decision_note     text CHECK (char_length(decision_note) <= 500),
            held_until        timestamptz,
            created_at        timestamptz NOT NULL DEFAULT now(),
            UNIQUE NULLS NOT DISTINCT (class_id, class_month_id, student_member_id),
            UNIQUE (tenant_id, id),
            CHECK (status <> 'approved' OR held_until IS NOT NULL),
            FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, class_id, class_month_id)
                REFERENCES class_months (tenant_id, class_id, id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id),
            FOREIGN KEY (tenant_id, decided_by) REFERENCES tenant_members (tenant_id, id)
        )
    """)
    op.execute("CREATE INDEX idx_seat_requests_status ON seat_requests (tenant_id, status, created_at)")
    op.execute("CREATE INDEX idx_seat_requests_student ON seat_requests (student_member_id)")
    op.execute("""
        CREATE TABLE seat_waits (
            id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id         uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
            class_id          uuid NOT NULL,
            student_member_id uuid NOT NULL,
            created_at        timestamptz NOT NULL DEFAULT now(),
            UNIQUE (class_id, student_member_id),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id)
        )
    """)
    op.execute("CREATE INDEX idx_seat_waits_student ON seat_waits (student_member_id)")
    for table, grants in (("seat_requests", "SELECT, INSERT, UPDATE"), ("seat_waits", "SELECT, INSERT, DELETE")):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} USING (tenant_id = current_tenant_id()) "
                   "WITH CHECK (tenant_id = current_tenant_id())")
        op.execute(_USER_POLICY.format(table=table))
        op.execute(f"GRANT {grants} ON {table} TO eduzone_app")

    op.execute(_SEAT_LAST_MONTH)
    op.execute(_SEAT_HOLDERS)
    op.execute("""
        CREATE FUNCTION seat_registration(p_registration text, p_after_start text, p_starts_on date) RETURNS text
        LANGUAGE sql STABLE SET search_path = public, pg_temp AS $$
            SELECT CASE WHEN p_after_start IS NOT NULL AND p_starts_on <= (now() AT TIME ZONE 'Asia/Colombo')::date
                        THEN p_after_start ELSE p_registration END
        $$
    """)
    op.execute(_PUBLIC_SEATS_TAKEN)
    for sig in ("seat_last_month(uuid, uuid)", "seat_holders(uuid, uuid)", "seat_registration(text, text, date)",
                "public_seats_taken(uuid, uuid)"):
        op.execute(f"REVOKE ALL ON FUNCTION {sig} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {sig} TO eduzone_app, eduzone_admin")
    op.execute("ALTER FUNCTION public_seats_taken(uuid, uuid) OWNER TO eduzone_admin")

    op.execute(_public_classes(_SEATED))
    op.execute(_PUBLIC_SEATS)
    op.execute("ALTER VIEW public_seats OWNER TO eduzone_admin")
    op.execute("GRANT SELECT ON public_seats TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP VIEW public_seats")
    op.execute(_public_classes(_JOINED))
    op.execute("DROP FUNCTION public_seats_taken(uuid, uuid)")
    op.execute("DROP FUNCTION seat_registration(text, text, date)")
    op.execute("DROP FUNCTION seat_holders(uuid, uuid)")
    op.execute("DROP FUNCTION seat_last_month(uuid, uuid)")
    op.execute("DROP TABLE seat_waits")
    op.execute("DROP TABLE seat_requests")
