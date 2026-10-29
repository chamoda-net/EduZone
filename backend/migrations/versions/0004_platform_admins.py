"""Platform admins: authenticator (TOTP) secret per EduZone staff member.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-30

Only eduzone_admin can read this table (default privileges); the tenant-facing app role
gets no grant, so a bug in tenant code can never read an admin's second factor.
"""

from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE platform_admins (
            user_id         uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            totp_secret     text NOT NULL,                 -- base32, for an authenticator app
            last_totp_step  bigint NOT NULL DEFAULT 0,     -- replay protection: each code works once
            created_at      timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON platform_admins TO eduzone_admin")
    op.execute("REVOKE ALL ON platform_admins FROM eduzone_app")


def downgrade() -> None:
    op.execute("DROP TABLE platform_admins")
