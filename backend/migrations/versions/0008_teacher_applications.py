"""Teacher self-registration and approval (migration phase 5).

Revision ID: 0008
Revises: 0007
Create Date: 2026-10-30

- teacher_applications (platform-level; RLS: the applicant's own rows only): one application per organization a user asks to open. The ID or
  business document lives in private storage (only its key is here); the bank account number is stored
  encrypted (app key from the environment) plus a masked copy for display.
- A new application creates a `pending` tenant. Pending tenants: the console works (draft mode), nothing
  is public and nothing can be published or sold until EduZone approves.
- user_is_staff_anywhere() counts pending tenants too (their owners are staff while they prepare).
- open_pending_tenant(): the one way the app role creates a tenant: always `pending`, with the applicant as
  its owner (SECURITY DEFINER, owned by eduzone_admin; the app role has no INSERT on tenants).
"""

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE teacher_applications (
            id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id              uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tenant_id            uuid NOT NULL UNIQUE REFERENCES tenants(id) ON DELETE CASCADE,
            kind                 text NOT NULL CHECK (kind IN ('individual', 'institute')),
            org_name             text NOT NULL CHECK (char_length(org_name) BETWEEN 2 AND 120),
            subject_ids          uuid[] NOT NULL DEFAULT '{}',
            experience           text CHECK (char_length(experience) <= 2000),
            document_key         text NOT NULL,            -- private storage key, never a public URL
            document_name        text NOT NULL,
            document_type        text NOT NULL,
            payout_bank_name     text NOT NULL CHECK (char_length(payout_bank_name) <= 80),
            payout_branch        text CHECK (char_length(payout_branch) <= 80),
            payout_account_name  text NOT NULL CHECK (char_length(payout_account_name) <= 120),
            payout_account_enc   text NOT NULL,            -- Fernet ciphertext of the account number
            payout_account_masked text NOT NULL,           -- e.g. '****4417'
            terms_version        text NOT NULL,
            status               text NOT NULL DEFAULT 'submitted'
                                 CHECK (status IN ('submitted', 'changes_requested', 'approved', 'rejected')),
            review_note          text CHECK (char_length(review_note) <= 2000),
            reviewed_by          uuid REFERENCES users(id),
            reviewed_at          timestamptz,
            submitted_at         timestamptz NOT NULL DEFAULT now(),
            created_at           timestamptz NOT NULL DEFAULT now(),
            updated_at           timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_applications_status ON teacher_applications (status, submitted_at)")
    op.execute("CREATE INDEX idx_applications_user ON teacher_applications (user_id, created_at DESC)")
    op.execute("""
        CREATE TRIGGER trg_teacher_applications_updated BEFORE UPDATE ON teacher_applications
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)
    # The app sees only the signed-in applicant's own rows (app.user_id, set by the onboarding service);
    # reviewing is done by the platform admin (eduzone_admin, BYPASSRLS).
    op.execute("ALTER TABLE teacher_applications ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE teacher_applications FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY applicant_own ON teacher_applications
            USING (user_id = current_user_id()) WITH CHECK (user_id = current_user_id())
    """)
    op.execute("GRANT SELECT, INSERT, UPDATE ON teacher_applications TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON teacher_applications TO eduzone_admin")

    op.execute("""
        CREATE OR REPLACE FUNCTION user_is_staff_anywhere(p_user uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
            SELECT EXISTS (
                SELECT 1 FROM tenant_members m JOIN tenants t ON t.id = m.tenant_id
                WHERE m.user_id = p_user AND m.status = 'active'
                  AND m.role IN ('owner','admin','teacher') AND t.status IN ('active', 'pending')
            )
        $$
    """)
    op.execute("ALTER FUNCTION user_is_staff_anywhere(uuid) OWNER TO eduzone_admin")

    op.execute("""
        CREATE FUNCTION open_pending_tenant(p_user uuid, p_name text, p_slug text, p_org_type text,
                                            p_display_name text) RETURNS uuid
        LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = public, pg_temp AS $$
        DECLARE v_tenant uuid;
        BEGIN
            IF p_org_type NOT IN ('individual', 'institute') THEN
                RAISE EXCEPTION 'org type % cannot be opened by an applicant', p_org_type;
            END IF;
            INSERT INTO tenants (name, slug, org_type, status) VALUES (p_name, p_slug, p_org_type, 'pending')
                RETURNING id INTO v_tenant;
            PERFORM set_config('app.tenant_id', v_tenant::text, true);
            INSERT INTO tenant_members (tenant_id, user_id, role, display_name)
                VALUES (v_tenant, p_user, 'owner', p_display_name);
            RETURN v_tenant;
        END
        $$
    """)
    op.execute("ALTER FUNCTION open_pending_tenant(uuid, text, text, text, text) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION open_pending_tenant(uuid, text, text, text, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION open_pending_tenant(uuid, text, text, text, text) TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS open_pending_tenant(uuid, text, text, text, text)")
    op.execute("""
        CREATE OR REPLACE FUNCTION user_is_staff_anywhere(p_user uuid) RETURNS boolean
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
            SELECT EXISTS (
                SELECT 1 FROM tenant_members m JOIN tenants t ON t.id = m.tenant_id
                WHERE m.user_id = p_user AND m.status = 'active'
                  AND m.role IN ('owner','admin','teacher') AND t.status = 'active'
            )
        $$
    """)
    op.execute("DROP TABLE teacher_applications")
