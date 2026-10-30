"""User-scoped reads and entity -> tenant lookup (migration phase 3).

Revision ID: 0006
Revises: 0005
Create Date: 2026-10-30

- current_user_id(): app.user_id, set (SET LOCAL) by user_transaction() for the student area.
- Extra SELECT-only RLS policies: with app.user_id set and no tenant, a session sees only the signed-in
  user's own rows (their memberships and the tenants they belong to, enrollments, grants, late
  requests, progress, orders, order items, payments). Writes still need the tenant policy.
- resolve_entity_tenant(kind, id): which tenant a class / month / lesson / resource / order belongs to,
  so /learn routes can open that tenant's transaction (the access rule then runs as before).
- Fix: user_is_staff_anywhere() is owned by eduzone_admin like the other lookups. As the
  migration role it was subject to forced RLS (and saw no members) unless that role is a superuser.
"""

from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | None = None
depends_on: str | None = None

_OWN_MEMBERS = "SELECT id FROM tenant_members WHERE user_id = current_user_id()"
_STUDENT_TABLES = ("class_enrollments", "access_grants", "late_month_requests", "lesson_progress", "orders")


def upgrade() -> None:
    op.execute("""
        CREATE FUNCTION current_user_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
        $$
    """)

    op.execute("CREATE POLICY user_own_rows ON tenant_members FOR SELECT USING (user_id = current_user_id())")
    op.execute("""
        CREATE POLICY user_member_of ON tenants FOR SELECT
            USING (id IN (SELECT tenant_id FROM tenant_members WHERE user_id = current_user_id()))
    """)
    for table in _STUDENT_TABLES:
        op.execute(f"""
            CREATE POLICY user_own_rows ON {table} FOR SELECT
                USING (student_member_id IN ({_OWN_MEMBERS}))
        """)
    for table in ("order_items", "payments"):
        op.execute(f"""
            CREATE POLICY user_own_rows ON {table} FOR SELECT
                USING (order_id IN (SELECT id FROM orders WHERE student_member_id IN ({_OWN_MEMBERS})))
        """)

    op.execute("""
        CREATE FUNCTION resolve_entity_tenant(p_kind text, p_id uuid) RETURNS uuid
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
            SELECT t.id FROM tenants t
            WHERE t.status = 'active' AND t.id = (
                CASE p_kind
                    WHEN 'class'    THEN (SELECT tenant_id FROM classes WHERE id = p_id)
                    WHEN 'month'    THEN (SELECT tenant_id FROM class_months WHERE id = p_id)
                    WHEN 'lesson'   THEN (SELECT tenant_id FROM lessons WHERE id = p_id)
                    WHEN 'resource' THEN (SELECT tenant_id FROM lesson_resources WHERE id = p_id)
                    WHEN 'order'    THEN (SELECT tenant_id FROM orders WHERE id = p_id)
                END)
        $$
    """)
    op.execute("ALTER FUNCTION resolve_entity_tenant(text, uuid) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION resolve_entity_tenant(text, uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION resolve_entity_tenant(text, uuid) TO eduzone_app")

    op.execute("ALTER FUNCTION user_is_staff_anywhere(uuid) OWNER TO eduzone_admin")


def downgrade() -> None:
    op.execute("DROP FUNCTION resolve_entity_tenant(text, uuid)")
    for table in (*_STUDENT_TABLES, "order_items", "payments", "tenant_members"):
        op.execute(f"DROP POLICY user_own_rows ON {table}")
    op.execute("DROP POLICY user_member_of ON tenants")
    op.execute("DROP FUNCTION current_user_id()")
