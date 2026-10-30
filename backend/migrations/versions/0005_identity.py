"""Identity (migration phase 2): one account across tenants.

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-30

- Sessions become per account: user_sessions loses tenant_id (and with it RLS). Existing
  sessions are deleted, so everyone signs in again.
- user_devices: devices that passed an SMS check; a sign-in from any other device needs a code.
- user_identities: external sign-in (Google), one row per provider subject.
- email_verifications, recovery_tokens: single-use links, stored as SHA-256 hashes.
- login_attempts: password sign-in throttling per email and per IP.
- users: optional profile fields for "About you".
- user_is_staff_anywhere(): the one-device rule exempts staff, and tenant_members is behind RLS.
"""

from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # --- Sessions: per account ------------------------------------------------------------
    op.execute("DELETE FROM user_sessions")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON user_sessions")
    op.execute("ALTER TABLE user_sessions NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_sessions DISABLE ROW LEVEL SECURITY")
    op.execute("DROP INDEX IF EXISTS idx_sessions_active")
    op.execute("ALTER TABLE user_sessions DROP COLUMN tenant_id")
    op.execute("CREATE INDEX idx_sessions_active ON user_sessions (user_id) WHERE revoked_at IS NULL")
    # The app never deletes sessions (revocation is an update).
    op.execute("REVOKE DELETE ON user_sessions FROM eduzone_app")

    # --- Devices that passed an SMS check --------------------------------------------------
    op.execute("""
        CREATE TABLE user_devices (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            device_id       text NOT NULL,
            user_agent      text,
            trusted_at      timestamptz NOT NULL DEFAULT now(),
            last_seen_at    timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, device_id)
        )
    """)

    # --- External identities (Google) ------------------------------------------------------
    op.execute("""
        CREATE TABLE user_identities (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            provider        text NOT NULL CHECK (provider IN ('google')),
            subject         text NOT NULL,
            email           citext,
            created_at      timestamptz NOT NULL DEFAULT now(),
            last_used_at    timestamptz NOT NULL DEFAULT now(),
            UNIQUE (provider, subject),
            UNIQUE (user_id, provider)
        )
    """)

    # --- Single-use links ------------------------------------------------------------------
    op.execute("""
        CREATE TABLE email_verifications (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            email           citext NOT NULL,
            token_hash      text NOT NULL UNIQUE,
            expires_at      timestamptz NOT NULL,
            used_at         timestamptz,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_email_verifications_user ON email_verifications (user_id, created_at DESC)")
    op.execute("""
        CREATE TABLE recovery_tokens (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash      text NOT NULL UNIQUE,
            expires_at      timestamptz NOT NULL,
            used_at         timestamptz,
            request_ip      inet,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_recovery_tokens_user ON recovery_tokens (user_id, created_at DESC)")

    # --- Password sign-in throttling -------------------------------------------------------
    op.execute("""
        CREATE TABLE login_attempts (
            id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            email           citext NOT NULL,
            ip_address      inet,
            succeeded       boolean NOT NULL,
            created_at      timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_login_attempts_email ON login_attempts (email, created_at DESC)")
    op.execute("CREATE INDEX idx_login_attempts_ip ON login_attempts (ip_address, created_at DESC)")

    # --- OTP purposes: device check and recovery -------------------------------------------
    op.execute("ALTER TABLE otp_codes DROP CONSTRAINT IF EXISTS otp_codes_purpose_check")
    op.execute("""
        ALTER TABLE otp_codes ADD CONSTRAINT otp_codes_purpose_check
            CHECK (purpose IN ('login','verify_phone','verify_email','reset_password','new_device'))
    """)

    # --- "About you" -----------------------------------------------------------------------
    op.execute("""
        ALTER TABLE users
            ADD COLUMN exam      text CHECK (exam IN ('grade_5','ol','al','other')),
            ADD COLUMN exam_year smallint CHECK (exam_year BETWEEN 2000 AND 2100),
            ADD COLUMN school    text CHECK (char_length(school) <= 120)
    """)

    # --- Grants ----------------------------------------------------------------------------
    op.execute("""
        GRANT SELECT, INSERT, UPDATE ON user_devices, user_identities, email_verifications,
            recovery_tokens TO eduzone_app
    """)
    op.execute("GRANT SELECT, INSERT ON login_attempts TO eduzone_app")
    op.execute("""
        GRANT INSERT (exam, exam_year, school) ON users TO eduzone_app;
        GRANT UPDATE (exam, exam_year, school) ON users TO eduzone_app;
    """)

    # The one-device rule exempts staff of any tenant; tenant_members is behind RLS, so the
    # check runs as the owner and returns only a yes/no.
    op.execute("""
        CREATE FUNCTION user_is_staff_anywhere(p_user uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
            SELECT EXISTS (
                SELECT 1 FROM tenant_members m JOIN tenants t ON t.id = m.tenant_id
                WHERE m.user_id = p_user AND m.status = 'active'
                  AND m.role IN ('owner','admin','teacher') AND t.status = 'active'
            )
        $$
    """)
    op.execute("REVOKE ALL ON FUNCTION user_is_staff_anywhere(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION user_is_staff_anywhere(uuid) TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION user_is_staff_anywhere(uuid)")
    op.execute("ALTER TABLE users DROP COLUMN exam, DROP COLUMN exam_year, DROP COLUMN school")
    op.execute("DELETE FROM otp_codes WHERE purpose = 'new_device'")
    op.execute("ALTER TABLE otp_codes DROP CONSTRAINT otp_codes_purpose_check")
    op.execute("""
        ALTER TABLE otp_codes ADD CONSTRAINT otp_codes_purpose_check
            CHECK (purpose IN ('login','verify_phone','verify_email','reset_password'))
    """)
    op.execute("DROP TABLE login_attempts, recovery_tokens, email_verifications, user_identities, user_devices")
    op.execute("DELETE FROM user_sessions")
    op.execute("ALTER TABLE user_sessions ADD COLUMN tenant_id uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE")
    op.execute("DROP INDEX IF EXISTS idx_sessions_active")
    op.execute("CREATE INDEX idx_sessions_active ON user_sessions (tenant_id, user_id) WHERE revoked_at IS NULL")
    op.execute("ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE user_sessions FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON user_sessions
            USING (tenant_id = current_tenant_id()) WITH CHECK (tenant_id = current_tenant_id())
    """)
    op.execute("GRANT DELETE ON user_sessions TO eduzone_app")
