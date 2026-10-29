"""Bunny Stream webhook: find the tenant that owns a video library.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-29

Same pattern as resolve_payment_tenant: the webhook arrives without a tenant host,
and RLS hides `tenants` until the tenant is known.
"""

from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE OR REPLACE FUNCTION resolve_bunny_library_tenant(p_library_id bigint)
        RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
            SELECT t.id FROM tenants t WHERE t.bunny_library_id = p_library_id
        $$
    """)
    op.execute("ALTER FUNCTION resolve_bunny_library_tenant(bigint) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION resolve_bunny_library_tenant(bigint) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION resolve_bunny_library_tenant(bigint) TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION resolve_bunny_library_tenant(bigint)")
