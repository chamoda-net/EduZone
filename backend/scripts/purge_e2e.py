"""Remove the organizations the Playwright smoke suite creates (slug `e2e-...`, from "a new user applies to teach").

Each run of that test opens a pending organization; the suite runs this after it finishes so the local database
doesn't fill up with them. Also removes the applicants' teacher profiles when they belong to no other organization.
The test students' accounts stay: their orders in the demo organization are in the ledger, which is append-only.

Runs as the schema owner with triggers paused (like the pytest cleanup). Local and test databases only.
"""

import psycopg

from app.core.config import get_settings


def main() -> None:
    s = get_settings()
    if s.environment != "local":
        raise SystemExit("purge_e2e.py runs only with ENVIRONMENT=local")
    url = s.migration_database_url.replace("postgresql+psycopg", "postgresql")
    with psycopg.connect(url) as conn:
        ids = [r[0] for r in conn.execute("SELECT id FROM tenants WHERE slug LIKE 'e2e-%'")]
        if not ids:
            print("no e2e organizations to remove")
            return
        owners = [r[0] for r in conn.execute(
            "SELECT DISTINCT user_id FROM tenant_members WHERE tenant_id = ANY(%s) AND role = 'owner'", (ids,))]
        conn.execute("SET session_replication_role = replica")   # skip triggers (append-only audit/ledger) and FKs
        tables = [r[0] for r in conn.execute("""
            SELECT c.relname FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
            WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relname <> 'tenants'
        """)]
        for table in tables:
            conn.execute(f"DELETE FROM {table} WHERE tenant_id = ANY(%s)", (ids,))  # type: ignore[arg-type]
        conn.execute("DELETE FROM tenants WHERE id = ANY(%s)", (ids,))
        conn.execute("""
            DELETE FROM teacher_profiles p WHERE p.user_id = ANY(%s)
              AND NOT EXISTS (SELECT 1 FROM tenant_members m WHERE m.user_id = p.user_id AND m.role <> 'student')
        """, (owners,))
        conn.execute("SET session_replication_role = origin")
    print(f"removed {len(ids)} e2e organization(s)")


if __name__ == "__main__":
    main()
