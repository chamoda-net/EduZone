from pathlib import Path

from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.db import AdminSession, AppSession

EXPECTED_TABLES = {
    "tenants", "users", "otp_codes", "gateway_webhook_events", "platform_admin_sessions",
    "tenant_members", "user_sessions", "classes", "class_months", "lessons", "media_assets",
    "lesson_resources", "class_enrollments", "late_month_requests", "access_grants",
    "lesson_progress", "orders", "order_items", "payments", "refunds", "payouts",
    "ledger_transactions", "ledger_entries", "tenant_usage_daily", "audit_logs",
    # identity (migration 0005)
    "user_devices", "user_identities", "email_verifications", "recovery_tokens", "login_attempts",
}


async def test_migrated_to_head() -> None:
    script = ScriptDirectory(str(Path(__file__).resolve().parents[1] / "migrations"))
    async with AdminSession() as session:
        version = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one()
        tables = set(
            (await session.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            ))).scalars()
        )
    assert version == script.get_current_head()
    assert EXPECTED_TABLES <= tables


async def test_app_role_is_subject_to_rls() -> None:
    async with AppSession() as session:
        role = (await session.execute(text("SELECT current_user"))).scalar_one()
        bypass = (await session.execute(text(
            "SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user"
        ))).scalar_one()
    assert role == "eduzone_app"
    assert bypass is False


async def test_admin_role_bypasses_rls() -> None:
    async with AdminSession() as session:
        role = (await session.execute(text("SELECT current_user"))).scalar_one()
    assert role == "eduzone_admin"
