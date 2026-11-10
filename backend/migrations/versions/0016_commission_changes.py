"""Courses, step C7 (docs/COURSES.md C.10): commission per product type, per-tenant overrides, scheduled changes.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-10

- platform_commission_rates: the default per product type (tuition, course), 20% each.
- tenants.tuition_commission_bps / course_commission_bps: an organization's override (NULL = the default).
  tenants.commission_bps is copied into both where it differs from 20%, and is no longer read.
- commission_changes: every change, announced with notice and applied on its date. Organizations read their own
  rows and the platform-wide ones (forced RLS); only eduzone_admin writes. One scheduled change per scope, tenant
  and kind. `notified` records which organizations' owners were told.
- commission_rate_for(tenant, kind) (SECURITY DEFINER, eduzone_admin only) and commission_rate(kind) (the current
  tenant, for checkout): the rate now, counting changes whose time has come even before they are marked applied,
  so no job is needed for checkout to be right.
"""

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE platform_commission_rates (
            kind            text PRIMARY KEY CHECK (kind IN ('tuition','course')),
            commission_bps  integer NOT NULL CHECK (commission_bps BETWEEN 0 AND 10000),
            updated_at      timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("INSERT INTO platform_commission_rates VALUES ('tuition', 2000, now()), ('course', 2000, now())")
    op.execute("GRANT SELECT ON platform_commission_rates TO eduzone_app")

    op.execute("""
        ALTER TABLE tenants
            ADD COLUMN tuition_commission_bps integer CHECK (tuition_commission_bps BETWEEN 0 AND 10000),
            ADD COLUMN course_commission_bps  integer CHECK (course_commission_bps BETWEEN 0 AND 10000)
    """)
    op.execute("""
        UPDATE tenants SET tuition_commission_bps = commission_bps, course_commission_bps = commission_bps
        WHERE commission_bps <> 2000
    """)

    op.execute("""
        CREATE TABLE commission_changes (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            scope           text NOT NULL CHECK (scope IN ('platform','tenant')),
            tenant_id       uuid REFERENCES tenants(id),
            kind            text NOT NULL CHECK (kind IN ('tuition','course')),
            old_bps         integer NOT NULL CHECK (old_bps BETWEEN 0 AND 10000),
            new_bps         integer NOT NULL CHECK (new_bps BETWEEN 0 AND 10000),
            reason          text NOT NULL CHECK (char_length(reason) BETWEEN 3 AND 1000),
            announced_at    timestamptz NOT NULL DEFAULT now(),
            effective_at    timestamptz NOT NULL,
            status          text NOT NULL DEFAULT 'scheduled' CHECK (status IN ('scheduled','applied','cancelled')),
            applied_at      timestamptz,
            cancelled_at    timestamptz,
            notified        jsonb NOT NULL DEFAULT '[]'::jsonb,
            created_by      uuid NOT NULL REFERENCES users(id),
            cancelled_by    uuid REFERENCES users(id),
            created_at      timestamptz NOT NULL DEFAULT now(),
            CHECK ((scope = 'platform' AND tenant_id IS NULL) OR (scope = 'tenant' AND tenant_id IS NOT NULL)),
            CHECK (effective_at > announced_at),
            CHECK (new_bps <> old_bps)
        )
    """)
    op.execute("CREATE INDEX idx_commission_changes_due ON commission_changes (effective_at) WHERE status = 'scheduled'")
    op.execute("""
        CREATE UNIQUE INDEX uq_commission_change_scheduled ON commission_changes (scope, tenant_id, kind)
            NULLS NOT DISTINCT WHERE status = 'scheduled'
    """)
    op.execute("ALTER TABLE commission_changes ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE commission_changes FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_read ON commission_changes FOR SELECT
                  USING (scope = 'platform' OR tenant_id = current_tenant_id())""")
    op.execute("GRANT SELECT ON commission_changes TO eduzone_app")

    op.execute("""
        CREATE FUNCTION commission_rate_for(p_tenant uuid, p_kind text) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
            SELECT COALESCE(
                (SELECT new_bps FROM commission_changes
                 WHERE scope = 'tenant' AND tenant_id = p_tenant AND kind = p_kind AND status = 'scheduled'
                   AND effective_at <= now()
                 ORDER BY effective_at DESC LIMIT 1),
                (SELECT CASE p_kind WHEN 'course' THEN course_commission_bps ELSE tuition_commission_bps END
                 FROM tenants WHERE id = p_tenant),
                (SELECT new_bps FROM commission_changes
                 WHERE scope = 'platform' AND kind = p_kind AND status = 'scheduled' AND effective_at <= now()
                 ORDER BY effective_at DESC LIMIT 1),
                (SELECT commission_bps FROM platform_commission_rates WHERE kind = p_kind)
            )
        $$
    """)
    op.execute("ALTER FUNCTION commission_rate_for(uuid, text) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION commission_rate_for(uuid, text) FROM PUBLIC")
    op.execute("""
        CREATE FUNCTION commission_rate(p_kind text) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
            SELECT commission_rate_for(current_tenant_id(), p_kind) WHERE current_tenant_id() IS NOT NULL
        $$
    """)
    op.execute("ALTER FUNCTION commission_rate(text) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION commission_rate(text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION commission_rate(text) TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION commission_rate(text)")
    op.execute("DROP FUNCTION commission_rate_for(uuid, text)")
    op.execute("DROP TABLE commission_changes")
    op.execute("ALTER TABLE tenants DROP COLUMN course_commission_bps, DROP COLUMN tuition_commission_bps")
    op.execute("DROP TABLE platform_commission_rates")
