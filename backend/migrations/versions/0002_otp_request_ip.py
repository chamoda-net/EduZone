"""OTP: record the requesting IP for per-IP rate limits.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29
"""

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("ALTER TABLE otp_codes ADD COLUMN request_ip inet")
    op.execute(
        "CREATE INDEX idx_otp_ip ON otp_codes (request_ip, created_at DESC) WHERE request_ip IS NOT NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX idx_otp_ip")
    op.execute("ALTER TABLE otp_codes DROP COLUMN request_ip")
