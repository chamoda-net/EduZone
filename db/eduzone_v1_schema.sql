-- =============================================================================
-- EduZone v1 — PostgreSQL schema
-- Target: PostgreSQL 16+
-- Scope : tuition teachers / institutes, monthly class fees, online gateway only,
--         EduZone collects payments, ledger gives each organization full visibility.
-- Multi-tenant from day one: every business row carries tenant_id, enforced by
-- composite foreign keys (no cross-tenant links) and Row-Level Security.
--
-- Conventions
--   * Money: BIGINT in cents (LKR 2,000.00 = 200000). Never DECIMAL/FLOAT.
--   * Rates: basis points (2000 = 20.00%).
--   * Status fields: TEXT + CHECK (easy to extend, readable in SQL).
--   * Time: TIMESTAMPTZ, stored UTC; display in Asia/Colombo.
--
-- Runtime roles (create once per cluster, see bottom of file)
--   eduzone_app   : the FastAPI app. Subject to RLS. Sets app.tenant_id per request.
--   eduzone_admin : EduZone platform console + background jobs. BYPASSRLS.
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;   -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS citext;     -- case-insensitive email

-- -----------------------------------------------------------------------------
-- Helpers
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END $$;

-- Current tenant for this request/transaction; NULL if not set.
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.tenant_id', true), '')::uuid
$$;

-- The student area (migration 0006): app.user_id set, no tenant -> only the user's own rows.
CREATE OR REPLACE FUNCTION current_user_id() RETURNS uuid
LANGUAGE sql STABLE AS $$
    SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;

-- =============================================================================
-- 1. PLATFORM LEVEL (not tenant-scoped)
-- =============================================================================

-- An organization using EduZone: a single teacher, an institute, or (later) a company.
CREATE TABLE tenants (
    id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name                    text NOT NULL,
    slug                    text NOT NULL UNIQUE                 -- subdomain: <slug>.eduzone.lk
                            CHECK (slug ~ '^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$'),
    org_type                text NOT NULL DEFAULT 'individual'
                            CHECK (org_type IN ('individual','institute','corporate')),
    status                  text NOT NULL DEFAULT 'active'
                            CHECK (status IN ('pending','active','suspended','closed')),
    currency                char(3) NOT NULL DEFAULT 'LKR',
    commission_bps          integer NOT NULL DEFAULT 2000        -- EduZone share, 20%
                            CHECK (commission_bps BETWEEN 0 AND 10000),
    gateway_fee_bearer      text NOT NULL DEFAULT 'tenant'       -- who absorbs gateway fees
                            CHECK (gateway_fee_bearer IN ('tenant','platform')),
    -- Branding (v1: logo/colours; landing page content comes in v1.1)
    logo_url                text,
    primary_color           char(7) CHECK (primary_color ~ '^#[0-9A-Fa-f]{6}$'),
    contact_email           citext,
    contact_phone           text,
    -- Bunny Stream: one video library per tenant => per-tenant usage and cost.
    -- The library API key lives in the secret manager, never in this table.
    bunny_library_id        bigint UNIQUE,
    -- Plan limits (aligned to Bunny cost). NULL = unlimited.
    storage_limit_bytes     bigint CHECK (storage_limit_bytes >= 0),
    bandwidth_limit_bytes   bigint CHECK (bandwidth_limit_bytes >= 0),  -- per calendar month
    -- Payout destination (display only; full bank details stay out of the DB)
    payout_bank_name        text,
    payout_account_masked   text,                                -- e.g. '****4417'
    created_at              timestamptz NOT NULL DEFAULT now(),
    updated_at              timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_tenants_updated BEFORE UPDATE ON tenants
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- A person. Global identity: one login can be a student in one tenant
-- and a teacher in another (roles live in tenant_members).
CREATE TABLE users (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    phone               text UNIQUE CHECK (phone ~ '^\+[1-9][0-9]{7,14}$'),  -- E.164
    email               citext UNIQUE,
    password_hash       text,                        -- NULL when OTP-only
    full_name           text NOT NULL,
    preferred_language  text NOT NULL DEFAULT 'en' CHECK (preferred_language IN ('en','si','ta')),
    is_platform_admin   boolean NOT NULL DEFAULT false,
    phone_verified_at   timestamptz,
    email_verified_at   timestamptz,
    last_login_at       timestamptz,
    -- "About you" (migration 0005), all optional
    exam                text CHECK (exam IN ('grade_5','ol','al','other')),
    exam_year           smallint CHECK (exam_year BETWEEN 2000 AND 2100),
    school              text CHECK (char_length(school) <= 120),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    CHECK (phone IS NOT NULL OR email IS NOT NULL)
);
CREATE TRIGGER trg_users_updated BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Platform admin login sessions. Separate from user_sessions (which is per tenant)
-- and reachable only through eduzone_admin.
CREATE TABLE platform_admin_sessions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash  text NOT NULL UNIQUE,
    ip_address          inet,
    user_agent          text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    last_seen_at        timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz NOT NULL,
    revoked_at          timestamptz,
    revoke_reason       text
);
CREATE INDEX idx_admin_sessions_active ON platform_admin_sessions (user_id) WHERE revoked_at IS NULL;

-- Authenticator (TOTP) second factor for platform admins (migration 0004). Admin role only.
CREATE TABLE platform_admins (
    user_id         uuid PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    totp_secret     text NOT NULL,                   -- base32, for an authenticator app
    last_totp_step  bigint NOT NULL DEFAULT 0,       -- replay protection: each code works once
    created_at      timestamptz NOT NULL DEFAULT now()
);

-- One-time passcodes for login / verification. Store only a hash of the code.
CREATE TABLE otp_codes (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    destination     text NOT NULL,                   -- phone or email
    -- 'login' = platform admin sign-in; 'new_device' = sign-in from an unknown device (migration 0005)
    purpose         text NOT NULL CHECK (purpose IN ('login','verify_phone','verify_email','reset_password','new_device')),
    code_hash       text NOT NULL,
    attempts        smallint NOT NULL DEFAULT 0,
    expires_at      timestamptz NOT NULL,
    consumed_at     timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now(),
    request_ip      inet                             -- per-IP rate limit (migration 0002)
);
CREATE INDEX idx_otp_lookup ON otp_codes (destination, purpose, created_at DESC);
CREATE INDEX idx_otp_ip ON otp_codes (request_ip, created_at DESC) WHERE request_ip IS NOT NULL;

-- Raw gateway webhooks, stored before processing. Unique event id = idempotency.
CREATE TABLE gateway_webhook_events (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    gateway         text NOT NULL,                   -- 'payhere', 'bank_ipg', ...
    event_ref       text NOT NULL,
    payload         jsonb NOT NULL,
    signature_ok    boolean NOT NULL,
    received_at     timestamptz NOT NULL DEFAULT now(),
    processed_at    timestamptz,
    process_error   text,
    UNIQUE (gateway, event_ref)
);

-- =============================================================================
-- 2. MEMBERSHIP & SESSIONS
-- =============================================================================

CREATE TABLE tenant_members (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role            text NOT NULL CHECK (role IN ('owner','admin','teacher','student')),
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('invited','active','suspended','left')),
    student_code    text,                            -- institute's own index number, optional
    display_name    text,                            -- e.g. teacher's public name
    bio             text,
    joined_at       timestamptz NOT NULL DEFAULT now(),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, user_id),
    UNIQUE (tenant_id, id),                          -- target for tenant-safe composite FKs
    UNIQUE (tenant_id, student_code)
);
CREATE INDEX idx_members_user ON tenant_members (user_id);
CREATE INDEX idx_members_role ON tenant_members (tenant_id, role, status);
CREATE TRIGGER trg_members_updated BEFORE UPDATE ON tenant_members
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Login sessions, per account (migration 0005: no tenant): the one-device rule and remote logout.
-- Platform-level, like users: no tenant_id, no RLS.
CREATE TABLE user_sessions (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id           text NOT NULL,               -- generated by the client, stored locally
    refresh_token_hash  text NOT NULL UNIQUE,
    ip_address          inet,
    user_agent          text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    last_seen_at        timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz NOT NULL,
    revoked_at          timestamptz,
    revoke_reason       text
);
CREATE INDEX idx_sessions_active ON user_sessions (user_id) WHERE revoked_at IS NULL;

-- Identity (migration 0005). Platform-level: one account across all tenants.
-- Devices that passed an SMS check; sign-in from any other device needs a code.
CREATE TABLE user_devices (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    device_id       text NOT NULL,
    user_agent      text,
    trusted_at      timestamptz NOT NULL DEFAULT now(),
    last_seen_at    timestamptz NOT NULL DEFAULT now(),
    UNIQUE (user_id, device_id)
);

-- External sign-in (Google), one row per provider subject.
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
);

-- Single-use email links, stored as SHA-256 hashes.
CREATE TABLE email_verifications (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email           citext NOT NULL,
    token_hash      text NOT NULL UNIQUE,
    expires_at      timestamptz NOT NULL,
    used_at         timestamptz,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_email_verifications_user ON email_verifications (user_id, created_at DESC);

CREATE TABLE recovery_tokens (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash      text NOT NULL UNIQUE,
    expires_at      timestamptz NOT NULL,
    used_at         timestamptz,
    request_ip      inet,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_recovery_tokens_user ON recovery_tokens (user_id, created_at DESC);

-- Password sign-in throttling per email and per IP.
CREATE TABLE login_attempts (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    email           citext NOT NULL,
    ip_address      inet,
    succeeded       boolean NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_login_attempts_email ON login_attempts (email, created_at DESC);
CREATE INDEX idx_login_attempts_ip ON login_attempts (ip_address, created_at DESC);

-- =============================================================================
-- 3. CATALOGUE: classes -> months -> lessons -> resources
-- =============================================================================

CREATE TABLE classes (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    teacher_member_id   uuid NOT NULL,                -- revenue attribution for institutes
    title               text NOT NULL,                -- '2027 A/L Physics - Theory'
    slug                text NOT NULL,
    description         text,
    subject             text,                         -- 'Physics'
    exam                text CHECK (exam IN ('grade_5','ol','al','other')),
    batch_year          smallint CHECK (batch_year BETWEEN 2000 AND 2100),
    medium              text CHECK (medium IN ('si','ta','en')),
    cover_image_url     text,
    pricing_model       text NOT NULL CHECK (pricing_model IN ('monthly','one_time','free')),
    monthly_fee_cents   bigint CHECK (monthly_fee_cents >= 0),
    one_time_price_cents bigint CHECK (one_time_price_cents >= 0),
    allow_late_months   boolean NOT NULL DEFAULT true,  -- students may REQUEST past months
    max_video_views     smallint CHECK (max_video_views > 0),  -- NULL = unlimited
    status              text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft','published','archived')),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, slug),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, teacher_member_id) REFERENCES tenant_members (tenant_id, id),
    CHECK (pricing_model <> 'monthly'  OR monthly_fee_cents   IS NOT NULL),
    CHECK (pricing_model <> 'one_time' OR one_time_price_cents IS NOT NULL)
);
CREATE INDEX idx_classes_teacher ON classes (tenant_id, teacher_member_id);
CREATE INDEX idx_classes_listing ON classes (tenant_id, status, exam, batch_year);
CREATE TRIGGER trg_classes_updated BEFORE UPDATE ON classes
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- One billable month of a monthly class. Paying for it unlocks its lessons.
CREATE TABLE class_months (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL,
    class_id        uuid NOT NULL,
    month_start     date NOT NULL CHECK (EXTRACT(DAY FROM month_start) = 1),  -- 2026-10-01
    fee_cents       bigint CHECK (fee_cents >= 0),     -- NULL = class.monthly_fee_cents
    status          text NOT NULL DEFAULT 'open' CHECK (status IN ('upcoming','open','closed')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (class_id, month_start),
    UNIQUE (tenant_id, id),
    UNIQUE (tenant_id, class_id, id),                -- target for "month belongs to this class" FKs
    FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id) ON DELETE CASCADE
);

-- A lesson: a live Zoom session, a recorded lesson, or a tute/paper.
-- Monthly classes: class_month_id is set. One-time/free classes: NULL.
CREATE TABLE lessons (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL,
    class_id        uuid NOT NULL,
    class_month_id  uuid,
    title           text NOT NULL,
    description     text,
    lesson_type     text NOT NULL CHECK (lesson_type IN ('live','recorded','document')),
    sort_order      integer NOT NULL DEFAULT 0,
    scheduled_at    timestamptz,                       -- live lessons
    duration_minutes smallint,
    zoom_join_url   text,                              -- shown only to students with access
    is_free_preview boolean NOT NULL DEFAULT false,
    is_published    boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, class_id)       REFERENCES classes (tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, class_id, class_month_id)
                                            REFERENCES class_months (tenant_id, class_id, id) ON DELETE CASCADE,
    CHECK (lesson_type <> 'live' OR scheduled_at IS NOT NULL)
);
CREATE INDEX idx_lessons_class ON lessons (tenant_id, class_id, class_month_id, sort_order);
CREATE INDEX idx_lessons_upcoming ON lessons (tenant_id, scheduled_at) WHERE lesson_type = 'live';
CREATE TRIGGER trg_lessons_updated BEFORE UPDATE ON lessons
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Uploaded media. Videos in Bunny Stream (tenant's library); PDFs in Bunny Storage.
CREATE TABLE media_assets (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    uploaded_by         uuid NOT NULL,                 -- tenant_members.id
    kind                text NOT NULL CHECK (kind IN ('video','document','image')),
    provider            text NOT NULL CHECK (provider IN ('bunny_stream','bunny_storage')),
    external_id         text NOT NULL,                 -- Bunny video GUID or storage path
    original_filename   text,
    mime_type           text,
    size_bytes          bigint NOT NULL DEFAULT 0 CHECK (size_bytes >= 0),
    duration_seconds    integer,
    status              text NOT NULL DEFAULT 'uploading'
                        CHECK (status IN ('uploading','processing','ready','failed','deleted')),
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (provider, external_id),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, uploaded_by) REFERENCES tenant_members (tenant_id, id)
);
CREATE INDEX idx_media_tenant ON media_assets (tenant_id, kind, status);
CREATE TRIGGER trg_media_updated BEFORE UPDATE ON media_assets
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- Attach media to a lesson (a live lesson can later get its recording + a tute).
CREATE TABLE lesson_resources (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL,
    lesson_id       uuid NOT NULL,
    media_asset_id  uuid NOT NULL,
    title           text,
    sort_order      integer NOT NULL DEFAULT 0,
    is_downloadable boolean NOT NULL DEFAULT false,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (lesson_id, media_asset_id),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, lesson_id)      REFERENCES lessons (tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, media_asset_id) REFERENCES media_assets (tenant_id, id)
);

-- =============================================================================
-- 4. ENROLMENT & ACCESS
-- =============================================================================

-- Student joined a class (needed for "who hasn't paid this month" lists).
CREATE TABLE class_enrollments (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    class_id            uuid NOT NULL,
    student_member_id   uuid NOT NULL,
    status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','left','removed')),
    enrolled_at         timestamptz NOT NULL DEFAULT now(),
    left_at             timestamptz,
    UNIQUE (class_id, student_member_id),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, class_id)          REFERENCES classes (tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id)
);
CREATE INDEX idx_enrollments_student ON class_enrollments (tenant_id, student_member_id);

-- Student asks to buy a month that is already over; teacher decides.
-- Approved request is what allows checkout for that past month.
CREATE TABLE late_month_requests (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    class_month_id      uuid NOT NULL,
    student_member_id   uuid NOT NULL,
    status              text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','approved','rejected','fulfilled','expired')),
    student_note        text,
    decided_by          uuid,                          -- tenant_members.id (teacher/admin)
    decided_at          timestamptz,
    decision_note       text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (class_month_id, student_member_id),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, class_month_id)    REFERENCES class_months (tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id),
    FOREIGN KEY (tenant_id, decided_by)        REFERENCES tenant_members (tenant_id, id)
);
CREATE INDEX idx_late_requests_pending ON late_month_requests (tenant_id, status) WHERE status = 'pending';

-- THE access table. Lesson access check:
--   monthly class  -> active grant for (student, lesson.class_month_id)
--   one-time class -> active grant for (student, class_id) with class_month_id NULL
CREATE TABLE access_grants (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    student_member_id   uuid NOT NULL,
    class_id            uuid NOT NULL,
    class_month_id      uuid,
    source              text NOT NULL CHECK (source IN ('purchase','manual','free','scholarship')),
    order_item_id       uuid,                          -- set when source = 'purchase'
    granted_by          uuid,                          -- tenant_members.id for manual grants
    granted_at          timestamptz NOT NULL DEFAULT now(),
    expires_at          timestamptz,                   -- optional: lock recordings after N months
    revoked_at          timestamptz,
    revoke_reason       text,
    FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id),
    FOREIGN KEY (tenant_id, class_id)          REFERENCES classes (tenant_id, id),
    FOREIGN KEY (tenant_id, class_id, class_month_id)
                                               REFERENCES class_months (tenant_id, class_id, id),
    FOREIGN KEY (tenant_id, granted_by)        REFERENCES tenant_members (tenant_id, id),
    CHECK (source <> 'purchase' OR order_item_id IS NOT NULL)
);
-- At most one live grant per student per month / per one-time class.
CREATE UNIQUE INDEX uq_grant_month ON access_grants (student_member_id, class_month_id)
    WHERE class_month_id IS NOT NULL AND revoked_at IS NULL;
CREATE UNIQUE INDEX uq_grant_class ON access_grants (student_member_id, class_id)
    WHERE class_month_id IS NULL AND revoked_at IS NULL;
CREATE INDEX idx_grants_class_month ON access_grants (tenant_id, class_month_id) WHERE revoked_at IS NULL;

-- Watching / view-limit tracking per student per lesson resource.
CREATE TABLE lesson_progress (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    student_member_id   uuid NOT NULL,
    lesson_resource_id  uuid NOT NULL,
    view_count          smallint NOT NULL DEFAULT 0,   -- compared to classes.max_video_views
    last_position_sec   integer NOT NULL DEFAULT 0,
    watched_seconds     integer NOT NULL DEFAULT 0,
    completed_at        timestamptz,
    last_viewed_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (student_member_id, lesson_resource_id),
    FOREIGN KEY (tenant_id, student_member_id)  REFERENCES tenant_members (tenant_id, id),
    FOREIGN KEY (tenant_id, lesson_resource_id) REFERENCES lesson_resources (tenant_id, id) ON DELETE CASCADE
);

-- =============================================================================
-- 5. ORDERS & PAYMENTS (online gateway only; no bank slips in v1)
-- =============================================================================

CREATE TABLE orders (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    student_member_id   uuid NOT NULL,
    order_no            text NOT NULL UNIQUE,          -- human readable, e.g. EZ-2610-000123
    status              text NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending','paid','failed','cancelled','refunded','partially_refunded')),
    currency            char(3) NOT NULL DEFAULT 'LKR',
    subtotal_cents      bigint NOT NULL CHECK (subtotal_cents >= 0),
    discount_cents      bigint NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
    total_cents         bigint NOT NULL CHECK (total_cents >= 0),
    paid_at             timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, student_member_id) REFERENCES tenant_members (tenant_id, id),
    CHECK (total_cents = subtotal_cents - discount_cents)
);
CREATE INDEX idx_orders_student ON orders (tenant_id, student_member_id, created_at DESC);
CREATE INDEX idx_orders_status ON orders (tenant_id, status, created_at DESC);
CREATE TRIGGER trg_orders_updated BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- One line per month / one-time class bought. Commission and teacher are
-- SNAPSHOTS at purchase time, so later rate changes never rewrite history.
CREATE TABLE order_items (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    order_id            uuid NOT NULL,
    class_id            uuid NOT NULL,
    class_month_id      uuid,
    teacher_member_id   uuid NOT NULL,
    late_request_id     uuid,
    description         text NOT NULL,                 -- 'Physics 2027 A/L - October 2026'
    amount_cents        bigint NOT NULL CHECK (amount_cents >= 0),
    commission_bps      integer NOT NULL CHECK (commission_bps BETWEEN 0 AND 10000),
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, order_id)          REFERENCES orders (tenant_id, id) ON DELETE CASCADE,
    FOREIGN KEY (tenant_id, class_id)          REFERENCES classes (tenant_id, id),
    FOREIGN KEY (tenant_id, class_id, class_month_id)
                                               REFERENCES class_months (tenant_id, class_id, id),
    FOREIGN KEY (tenant_id, teacher_member_id) REFERENCES tenant_members (tenant_id, id),
    FOREIGN KEY (tenant_id, late_request_id)   REFERENCES late_month_requests (tenant_id, id)
);
CREATE INDEX idx_order_items_order ON order_items (tenant_id, order_id);

ALTER TABLE access_grants
    ADD FOREIGN KEY (tenant_id, order_item_id) REFERENCES order_items (tenant_id, id);

-- One row per gateway attempt for an order.
CREATE TABLE payments (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    order_id            uuid NOT NULL,
    gateway             text NOT NULL,                 -- 'payhere', 'bank_ipg', ...
    gateway_payment_ref text,                          -- gateway's id, set on callback
    idempotency_key     text NOT NULL UNIQUE,
    amount_cents        bigint NOT NULL CHECK (amount_cents >= 0),
    gateway_fee_cents   bigint CHECK (gateway_fee_cents >= 0),  -- fee booked with the sale (estimate until settled)
    status              text NOT NULL DEFAULT 'initiated'
                        CHECK (status IN ('initiated','succeeded','failed','cancelled','refunded')),
    method              text,                          -- 'visa', 'master', 'amex', 'ezcash', ...
    card_last4          char(4),                       -- display only; never full card data
    failure_reason      text,
    created_at          timestamptz NOT NULL DEFAULT now(),
    updated_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (gateway, gateway_payment_ref),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, order_id) REFERENCES orders (tenant_id, id)
);
CREATE INDEX idx_payments_order ON payments (tenant_id, order_id);
CREATE TRIGGER trg_payments_updated BEFORE UPDATE ON payments
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TABLE refunds (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL,
    payment_id          uuid NOT NULL,
    order_item_id       uuid,                          -- NULL = whole payment
    amount_cents        bigint NOT NULL CHECK (amount_cents > 0),
    reason              text NOT NULL,
    status              text NOT NULL DEFAULT 'requested'
                        CHECK (status IN ('requested','approved','processed','rejected')),
    requested_by        uuid,                          -- tenant_members.id
    gateway_refund_ref  text,
    processed_at        timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, payment_id)    REFERENCES payments (tenant_id, id),
    FOREIGN KEY (tenant_id, order_item_id) REFERENCES order_items (tenant_id, id),
    FOREIGN KEY (tenant_id, requested_by)  REFERENCES tenant_members (tenant_id, id)
);

-- Money EduZone sends to the organization's bank account.
CREATE TABLE payouts (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           uuid NOT NULL REFERENCES tenants(id),
    amount_cents        bigint NOT NULL CHECK (amount_cents > 0),
    period_start        date NOT NULL,
    period_end          date NOT NULL CHECK (period_end >= period_start),
    status              text NOT NULL DEFAULT 'scheduled'
                        CHECK (status IN ('scheduled','sent','failed','cancelled')),
    bank_reference      text,                          -- transfer ref shown to the tenant
    created_by          uuid REFERENCES users(id),     -- EduZone admin
    sent_at             timestamptz,
    created_at          timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id)
);
CREATE INDEX idx_payouts_tenant ON payouts (tenant_id, created_at DESC);

-- =============================================================================
-- 6. LEDGER — source of truth for cash-flow visibility
-- Double entry: every ledger_transaction's entries sum to zero.
-- Sign: positive = debit, negative = credit.
--
-- Accounts
--   gateway_clearing    money held at / settled from the gateway   (EduZone asset)
--   gateway_fees        fees charged by the gateway                 (expense)
--   platform_commission EduZone's revenue                           (income)
--   tenant_payable      what EduZone owes the organization          (liability, per tenant)
--   bank                EduZone bank account                        (asset)
--
-- Example: Rs 2,000 month fee, 20% commission, Rs 60 gateway fee borne by tenant
--   gateway_clearing     +194000
--   gateway_fees           +6000
--   platform_commission   -40000
--   tenant_payable       -160000
--   tenant_payable         +6000   (fee recovered from tenant)
--   gateway_fees           -6000
--   => tenant net = 154000 (Rs 1,540)
-- =============================================================================

CREATE TABLE ledger_transactions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       uuid NOT NULL REFERENCES tenants(id),
    kind            text NOT NULL CHECK (kind IN ('sale','refund','payout','adjustment','fee_settlement')),
    payment_id      uuid,
    refund_id       uuid,
    payout_id       uuid,
    memo            text,
    occurred_at     timestamptz NOT NULL DEFAULT now(),
    created_by      uuid REFERENCES users(id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, id),
    FOREIGN KEY (tenant_id, payment_id) REFERENCES payments (tenant_id, id),
    FOREIGN KEY (tenant_id, refund_id)  REFERENCES refunds (tenant_id, id),
    FOREIGN KEY (tenant_id, payout_id)  REFERENCES payouts (tenant_id, id)
);
CREATE INDEX idx_ledger_tx_tenant ON ledger_transactions (tenant_id, occurred_at DESC);
-- A payment / refund / payout is booked exactly once.
CREATE UNIQUE INDEX uq_ledger_sale   ON ledger_transactions (payment_id) WHERE kind = 'sale';
CREATE UNIQUE INDEX uq_ledger_refund ON ledger_transactions (refund_id)  WHERE kind = 'refund';
CREATE UNIQUE INDEX uq_ledger_payout ON ledger_transactions (payout_id)  WHERE kind = 'payout';
-- The estimated fee booked with a sale is trued up at most once per payment.
CREATE UNIQUE INDEX uq_ledger_fee_settlement ON ledger_transactions (payment_id) WHERE kind = 'fee_settlement';

CREATE TABLE ledger_entries (
    id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id           uuid NOT NULL,
    ledger_tx_id        uuid NOT NULL,
    account             text NOT NULL CHECK (account IN
                        ('gateway_clearing','gateway_fees','platform_commission','tenant_payable','bank')),
    amount_cents        bigint NOT NULL CHECK (amount_cents <> 0),
    order_item_id       uuid,                          -- line-level detail
    teacher_member_id   uuid,                          -- per-teacher revenue for institutes
    FOREIGN KEY (tenant_id, ledger_tx_id)      REFERENCES ledger_transactions (tenant_id, id),
    FOREIGN KEY (tenant_id, order_item_id)     REFERENCES order_items (tenant_id, id),
    FOREIGN KEY (tenant_id, teacher_member_id) REFERENCES tenant_members (tenant_id, id)
);
CREATE INDEX idx_ledger_entries_tx ON ledger_entries (ledger_tx_id);
CREATE INDEX idx_ledger_entries_acct ON ledger_entries (tenant_id, account);
CREATE INDEX idx_ledger_entries_teacher ON ledger_entries (tenant_id, teacher_member_id)
    WHERE teacher_member_id IS NOT NULL;

-- Enforce balance at COMMIT (deferred), so entries can be inserted one by one.
CREATE OR REPLACE FUNCTION ledger_check_balanced() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    v_sum bigint;
BEGIN
    SELECT COALESCE(SUM(amount_cents), 0) INTO v_sum
    FROM ledger_entries WHERE ledger_tx_id = NEW.ledger_tx_id;
    IF v_sum <> 0 THEN
        RAISE EXCEPTION 'ledger transaction % is unbalanced by % cents', NEW.ledger_tx_id, v_sum;
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER trg_ledger_balanced
    AFTER INSERT OR UPDATE ON ledger_entries
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ledger_check_balanced();

-- A transaction with no entries would pass the balance check, so reject it at COMMIT.
CREATE OR REPLACE FUNCTION ledger_check_has_entries() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM ledger_entries WHERE ledger_tx_id = NEW.id) THEN
        RAISE EXCEPTION 'ledger transaction % has no entries', NEW.id;
    END IF;
    RETURN NULL;
END $$;
CREATE CONSTRAINT TRIGGER trg_ledger_tx_has_entries
    AFTER INSERT ON ledger_transactions
    DEFERRABLE INITIALLY DEFERRED
    FOR EACH ROW EXECUTE FUNCTION ledger_check_has_entries();

-- The ledger is append-only: corrections are new 'adjustment' transactions.
CREATE OR REPLACE FUNCTION ledger_block_changes() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'ledger is append-only; post an adjustment instead';
END $$;
CREATE TRIGGER trg_ledger_entries_immutable BEFORE UPDATE OR DELETE ON ledger_entries
    FOR EACH ROW EXECUTE FUNCTION ledger_block_changes();
CREATE TRIGGER trg_ledger_tx_immutable BEFORE UPDATE OR DELETE ON ledger_transactions
    FOR EACH ROW EXECUTE FUNCTION ledger_block_changes();

-- =============================================================================
-- 7. USAGE & AUDIT
-- =============================================================================

-- Daily snapshot pulled from the Bunny API per tenant library (cost control).
CREATE TABLE tenant_usage_daily (
    tenant_id           uuid NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    usage_date          date NOT NULL,
    storage_bytes       bigint NOT NULL DEFAULT 0,
    bandwidth_bytes     bigint NOT NULL DEFAULT 0,     -- delivered that day
    video_views         integer NOT NULL DEFAULT 0,
    PRIMARY KEY (tenant_id, usage_date)
);

CREATE TABLE audit_logs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tenant_id       uuid REFERENCES tenants(id),       -- NULL = platform-level action
    actor_user_id   uuid REFERENCES users(id),
    action          text NOT NULL,                     -- 'class.publish', 'late_request.approve', ...
    entity_type     text NOT NULL,
    entity_id       uuid,
    details         jsonb,
    ip_address      inet,
    created_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_tenant ON audit_logs (tenant_id, created_at DESC);
CREATE INDEX idx_audit_entity ON audit_logs (entity_type, entity_id);

-- =============================================================================
-- 8. CASH-FLOW VIEWS (what the organization sees)
-- security_invoker => the caller's RLS applies, so a tenant sees only itself.
-- =============================================================================

-- Per tenant, per month. Gross sales are shown as sold; refunds are their own line;
-- commission and net are AFTER refunds and fee true-ups (labels must say so).
--   gross_sales_cents        what students paid (sale transactions only)
--   refunds_cents            what was refunded to students
--   gateway_fees_cents       fees charged by the gateway, incl. fee_settlement true-ups
--   eduzone_commission_cents commission, net of refunded commission
--   net_earned_cents         tenant's earnings after fees and refunds
--   paid_out_cents           sent to the tenant's bank
CREATE VIEW v_tenant_cashflow_monthly WITH (security_invoker = true) AS
SELECT
    lt.tenant_id,
    date_trunc('month', lt.occurred_at AT TIME ZONE 'Asia/Colombo')::date AS month,
    SUM(CASE WHEN lt.kind = 'sale'   AND le.account = 'gateway_clearing' THEN le.amount_cents ELSE 0 END)
      + SUM(CASE WHEN lt.kind = 'sale' AND le.account = 'gateway_fees' AND le.amount_cents > 0 THEN le.amount_cents ELSE 0 END)
                                                                                    AS gross_sales_cents,
    -SUM(CASE WHEN lt.kind = 'refund' AND le.account = 'gateway_clearing' THEN le.amount_cents ELSE 0 END)
                                                                                    AS refunds_cents,
    SUM(CASE WHEN lt.kind = 'sale'   AND le.account = 'gateway_fees' AND le.amount_cents > 0 THEN le.amount_cents ELSE 0 END)
      - SUM(CASE WHEN lt.kind = 'fee_settlement' AND le.account = 'gateway_clearing' THEN le.amount_cents ELSE 0 END)
                                                                                    AS gateway_fees_cents,
    -SUM(CASE WHEN le.account = 'platform_commission' THEN le.amount_cents ELSE 0 END)
                                                                                    AS eduzone_commission_cents,
    -SUM(CASE WHEN lt.kind IN ('sale','refund','fee_settlement','adjustment') AND le.account = 'tenant_payable'
              THEN le.amount_cents ELSE 0 END)
                                                                                    AS net_earned_cents,
    SUM(CASE WHEN lt.kind = 'payout' AND le.account = 'tenant_payable' THEN le.amount_cents ELSE 0 END)
                                                                                    AS paid_out_cents
FROM ledger_transactions lt
JOIN ledger_entries le ON le.ledger_tx_id = lt.id
GROUP BY lt.tenant_id, 2;

-- What EduZone currently owes each tenant.
CREATE VIEW v_tenant_balance WITH (security_invoker = true) AS
SELECT tenant_id, -SUM(amount_cents) AS balance_due_cents
FROM ledger_entries
WHERE account = 'tenant_payable'
GROUP BY tenant_id;

-- Per-teacher net earnings inside an institute (institute pays teachers itself).
CREATE VIEW v_teacher_earnings_monthly WITH (security_invoker = true) AS
SELECT
    le.tenant_id,
    le.teacher_member_id,
    date_trunc('month', lt.occurred_at AT TIME ZONE 'Asia/Colombo')::date AS month,
    -SUM(le.amount_cents) AS net_earned_cents
FROM ledger_entries le
JOIN ledger_transactions lt ON lt.id = le.ledger_tx_id
WHERE le.account = 'tenant_payable'
  AND le.teacher_member_id IS NOT NULL
  AND lt.kind IN ('sale','refund','fee_settlement','adjustment')
GROUP BY le.tenant_id, le.teacher_member_id, 3;

-- =============================================================================
-- 9. ROW-LEVEL SECURITY
-- The app runs every request as:  BEGIN; SET LOCAL app.tenant_id = '<uuid>'; ...
-- If app.tenant_id is unset, current_tenant_id() is NULL and no rows match.
-- =============================================================================
DO $$
DECLARE
    t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'tenant_members','classes','class_months','lessons',
        'media_assets','lesson_resources','class_enrollments','late_month_requests',
        'access_grants','lesson_progress','orders','order_items','payments','refunds',
        'payouts','ledger_transactions','ledger_entries','tenant_usage_daily','audit_logs'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format(
            'CREATE POLICY tenant_isolation ON %I
                 USING (tenant_id = current_tenant_id())
                 WITH CHECK (tenant_id = current_tenant_id())', t);
    END LOOP;
END $$;

-- tenants: a tenant session may read only its own row; writes are platform-only.
ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
ALTER TABLE tenants FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_self_read ON tenants FOR SELECT USING (id = current_tenant_id());

-- =============================================================================
-- 10. ROLES & GRANTS (run once per cluster; passwords set outside this file)
-- =============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eduzone_app') THEN
        CREATE ROLE eduzone_app LOGIN;
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'eduzone_admin') THEN
        CREATE ROLE eduzone_admin LOGIN BYPASSRLS;
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO eduzone_app, eduzone_admin;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO eduzone_admin;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO eduzone_app, eduzone_admin;

-- Tables and sequences created later by migrations (run as this same owner role).
-- eduzone_app gets no default: each migration grants it exactly what it needs.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO eduzone_admin;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE ON SEQUENCES TO eduzone_app, eduzone_admin;

-- App: normal CRUD on catalogue, enrolment and session data...
GRANT SELECT, INSERT, UPDATE, DELETE ON
    tenant_members, classes, class_months, lessons, media_assets,
    lesson_resources, class_enrollments, late_month_requests, access_grants,
    lesson_progress
TO eduzone_app;
-- Identity (migration 0005): sessions are revoked, never deleted.
GRANT SELECT, INSERT, UPDATE ON user_sessions, user_devices, user_identities, email_verifications,
    recovery_tokens TO eduzone_app;
GRANT SELECT, INSERT ON login_attempts TO eduzone_app;
-- ...no DELETE on money records (status changes only); order lines are snapshots...
GRANT SELECT, INSERT, UPDATE ON orders, payments, refunds TO eduzone_app;
GRANT SELECT, INSERT ON order_items TO eduzone_app;
-- ...insert-only on money history and the audit trail, read-only on platform-owned data.
GRANT SELECT, INSERT ON ledger_transactions, ledger_entries, audit_logs TO eduzone_app;
GRANT SELECT ON tenants, payouts, tenant_usage_daily TO eduzone_app;
GRANT SELECT, INSERT, UPDATE ON otp_codes, gateway_webhook_events TO eduzone_app;
-- users: the app can never set is_platform_admin (column-level grants).
GRANT SELECT ON users TO eduzone_app;
GRANT INSERT (phone, email, password_hash, full_name, preferred_language,
              phone_verified_at, email_verified_at, last_login_at, exam, exam_year, school)
    ON users TO eduzone_app;
GRANT UPDATE (phone, email, password_hash, full_name, preferred_language,
              phone_verified_at, email_verified_at, last_login_at, updated_at, exam, exam_year, school)
    ON users TO eduzone_app;
-- platform_admin_sessions: no grant to eduzone_app at all.
GRANT SELECT ON v_tenant_cashflow_monthly, v_tenant_balance, v_teacher_earnings_monthly
    TO eduzone_app, eduzone_admin;

-- =============================================================================
-- 11. LOOKUPS BEFORE TENANT CONTEXT
-- Two things must be found before app.tenant_id can be set, and RLS would hide
-- them from eduzone_app. These SECURITY DEFINER functions are owned by
-- eduzone_admin (BYPASSRLS) and return only the minimum needed.
-- =============================================================================

-- Host header -> tenant. The caller turns unknown / non-active into 404.
CREATE OR REPLACE FUNCTION resolve_tenant(p_slug text)
RETURNS TABLE (id uuid, status text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT t.id, t.status FROM tenants t WHERE t.slug = lower(p_slug)
$$;

-- Gateway webhook -> tenant of the payment. The gateway echoes back the
-- reference we sent it (payments.idempotency_key). The webhook handler then
-- opens a normal tenant transaction with SET LOCAL app.tenant_id.
CREATE OR REPLACE FUNCTION resolve_payment_tenant(p_gateway text, p_idempotency_key text)
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT p.tenant_id FROM payments p
    WHERE p.gateway = p_gateway AND p.idempotency_key = p_idempotency_key
$$;

ALTER FUNCTION resolve_tenant(text) OWNER TO eduzone_admin;
ALTER FUNCTION resolve_payment_tenant(text, text) OWNER TO eduzone_admin;
REVOKE ALL ON FUNCTION resolve_tenant(text), resolve_payment_tenant(text, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_tenant(text), resolve_payment_tenant(text, text) TO eduzone_app;

-- Bunny Stream webhook -> tenant that owns the video library (migration 0003).
CREATE OR REPLACE FUNCTION resolve_bunny_library_tenant(p_library_id bigint)
RETURNS uuid
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
    SELECT t.id FROM tenants t WHERE t.bunny_library_id = p_library_id
$$;
ALTER FUNCTION resolve_bunny_library_tenant(bigint) OWNER TO eduzone_admin;
REVOKE ALL ON FUNCTION resolve_bunny_library_tenant(bigint) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_bunny_library_tenant(bigint) TO eduzone_app;

-- The one-device rule exempts staff of any tenant; tenant_members is behind RLS, so this runs as
-- the owner and returns only a yes/no (migration 0005).
CREATE OR REPLACE FUNCTION user_is_staff_anywhere(p_user uuid) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
    SELECT EXISTS (
        SELECT 1 FROM tenant_members m JOIN tenants t ON t.id = m.tenant_id
        WHERE m.user_id = p_user AND m.status = 'active'
          AND m.role IN ('owner','admin','teacher') AND t.status = 'active'
    )
$$;
REVOKE ALL ON FUNCTION user_is_staff_anywhere(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION user_is_staff_anywhere(uuid) TO eduzone_app;

-- User-scoped reads (migration 0006): SELECT-only policies, OR-ed with tenant_isolation. With app.user_id
-- set and no tenant, a session sees only the user's own rows. Never set both in one transaction.
CREATE POLICY user_own_rows ON tenant_members FOR SELECT USING (user_id = current_user_id());
CREATE POLICY user_member_of ON tenants FOR SELECT
    USING (id IN (SELECT tenant_id FROM tenant_members WHERE user_id = current_user_id()));
CREATE POLICY user_own_rows ON class_enrollments FOR SELECT
    USING (student_member_id IN (SELECT id FROM tenant_members WHERE user_id = current_user_id()));
CREATE POLICY user_own_rows ON access_grants FOR SELECT
    USING (student_member_id IN (SELECT id FROM tenant_members WHERE user_id = current_user_id()));
CREATE POLICY user_own_rows ON late_month_requests FOR SELECT
    USING (student_member_id IN (SELECT id FROM tenant_members WHERE user_id = current_user_id()));
CREATE POLICY user_own_rows ON lesson_progress FOR SELECT
    USING (student_member_id IN (SELECT id FROM tenant_members WHERE user_id = current_user_id()));
CREATE POLICY user_own_rows ON orders FOR SELECT
    USING (student_member_id IN (SELECT id FROM tenant_members WHERE user_id = current_user_id()));
CREATE POLICY user_own_rows ON order_items FOR SELECT
    USING (order_id IN (SELECT id FROM orders WHERE student_member_id IN
                        (SELECT id FROM tenant_members WHERE user_id = current_user_id())));
CREATE POLICY user_own_rows ON payments FOR SELECT
    USING (order_id IN (SELECT id FROM orders WHERE student_member_id IN
                        (SELECT id FROM tenant_members WHERE user_id = current_user_id())));

-- Which tenant a class / month / lesson / resource / order belongs to (active tenants only), so the
-- student area can open that tenant's transaction (migration 0006).
CREATE OR REPLACE FUNCTION resolve_entity_tenant(p_kind text, p_id uuid) RETURNS uuid
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
$$;
ALTER FUNCTION resolve_entity_tenant(text, uuid) OWNER TO eduzone_admin;
REVOKE ALL ON FUNCTION resolve_entity_tenant(text, uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_entity_tenant(text, uuid) TO eduzone_app;
ALTER FUNCTION user_is_staff_anywhere(uuid) OWNER TO eduzone_admin;

-- =============================================================================
-- MARKETPLACE (migration 0007)
-- =============================================================================
-- First URL segments the web app uses; a subject slug can never be one of them.
CREATE OR REPLACE FUNCTION is_reserved_slug(p_slug text) RETURNS boolean
LANGUAGE sql IMMUTABLE AS $$ SELECT p_slug = ANY (ARRAY['about','account','admin','api','assets','cart','checkout',
    'classes','contact','design','help','institutes','learn','lessons','login','logout','my','org','payments','privacy',
    'qr','recover','refund-policy','register','robots.txt','search','sitemap.xml','static','teach','teachers','terms',
    'verify-email','verify-phone']) $$;

CREATE TABLE subjects (                              -- EduZone-managed; the slug is the URL (/physics)
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    slug        text NOT NULL UNIQUE
                CHECK (slug ~ '^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])$' AND NOT is_reserved_slug(slug)),
    name        text NOT NULL,
    sort_order  integer NOT NULL DEFAULT 0,
    is_active   boolean NOT NULL DEFAULT true,
    created_at  timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE classes ADD COLUMN subject_id uuid REFERENCES subjects(id);
CREATE INDEX idx_classes_subject ON classes (subject_id) WHERE status = 'published';
ALTER TABLE tenants ADD COLUMN is_listed boolean NOT NULL DEFAULT true;

-- One public profile per person (platform-level): /<subject>/<slug>.
CREATE TABLE teacher_profiles (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      uuid NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    slug         text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$'),
    display_name text NOT NULL CHECK (char_length(display_name) BETWEEN 1 AND 80),
    headline     text CHECK (char_length(headline) <= 120),
    bio          text CHECK (char_length(bio) <= 2000),
    photo_url    text,
    highlights   text[] NOT NULL DEFAULT '{}' CHECK (cardinality(highlights) <= 6),
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now()
);
CREATE TRIGGER trg_teacher_profiles_updated BEFORE UPDATE ON teacher_profiles
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
GRANT SELECT ON subjects TO eduzone_app;
GRANT SELECT, INSERT, UPDATE ON teacher_profiles TO eduzone_app;

-- The public read path: views owned by eduzone_admin (BYPASSRLS) exposing public fields only, for active,
-- listed tenants and published classes with a subject and a teacher profile. The app role may only SELECT.
CREATE VIEW public_classes AS
SELECT c.id, c.slug, c.title, c.description, c.exam, c.batch_year, c.medium, c.cover_image_url,
       c.pricing_model, c.monthly_fee_cents, c.one_time_price_cents, c.created_at,
       t.currency, t.id AS tenant_id, t.slug AS org_slug, t.name AS org_name, t.org_type,
       s.id AS subject_id, s.slug AS subject_slug, s.name AS subject_name,
       tp.slug AS teacher_slug, tp.display_name AS teacher_name, tp.photo_url AS teacher_photo_url,
       tp.headline AS teacher_headline,
       om.id AS open_month_id, om.month_start AS open_month_start,
       COALESCE(om.fee_cents, c.monthly_fee_cents) AS open_month_fee_cents,
       EXISTS (SELECT 1 FROM lessons l WHERE l.class_id = c.id AND l.is_published AND l.lesson_type = 'live')
           AS has_live,
       EXISTS (SELECT 1 FROM lessons l WHERE l.class_id = c.id AND l.is_published AND l.lesson_type = 'recorded')
           AS has_recorded,
       EXISTS (SELECT 1 FROM lessons l WHERE l.class_id = c.id AND l.is_published AND l.is_free_preview)
           AS has_free_preview,
       (SELECT count(*) FROM class_enrollments e WHERE e.class_id = c.id AND e.status = 'active') AS students,
       to_tsvector('simple', coalesce(c.title, '') || ' ' || s.name || ' ' || tp.display_name || ' '
                   || t.name || ' ' || coalesce(c.description, '')) AS search
FROM classes c
JOIN tenants t ON t.id = c.tenant_id AND t.status = 'active' AND t.is_listed
JOIN subjects s ON s.id = c.subject_id AND s.is_active
JOIN tenant_members tm ON tm.tenant_id = c.tenant_id AND tm.id = c.teacher_member_id
JOIN teacher_profiles tp ON tp.user_id = tm.user_id
LEFT JOIN LATERAL (
    SELECT m.id, m.month_start, m.fee_cents FROM class_months m
    WHERE m.class_id = c.id AND m.status = 'open' ORDER BY m.month_start LIMIT 1
) om ON true
WHERE c.status = 'published';
CREATE VIEW public_class_months AS
SELECT m.id, m.class_id, m.month_start, m.status, COALESCE(m.fee_cents, pc.monthly_fee_cents) AS fee_cents,
       pc.currency
FROM class_months m JOIN public_classes pc ON pc.id = m.class_id;
CREATE VIEW public_lessons AS
SELECT l.id, l.class_id, l.class_month_id, l.title, l.lesson_type, l.sort_order, l.scheduled_at,
       l.duration_minutes, l.is_free_preview
FROM lessons l JOIN public_classes pc ON pc.id = l.class_id
WHERE l.is_published;
CREATE VIEW public_teachers AS
SELECT tp.slug, tp.display_name, tp.headline, tp.bio, tp.photo_url, tp.highlights,
       count(pc.id) AS class_count,
       array_agg(DISTINCT pc.subject_slug) AS subject_slugs,
       array_agg(DISTINCT pc.subject_name) AS subject_names,
       array_agg(DISTINCT pc.medium) FILTER (WHERE pc.medium IS NOT NULL) AS mediums,
       sum(pc.students) AS students
FROM teacher_profiles tp JOIN public_classes pc ON pc.teacher_slug = tp.slug
GROUP BY tp.slug, tp.display_name, tp.headline, tp.bio, tp.photo_url, tp.highlights;
CREATE VIEW public_institutes AS
SELECT t.slug, t.name, t.logo_url, count(pc.id) AS class_count,
       array_agg(DISTINCT pc.subject_name) AS subject_names,
       count(DISTINCT pc.teacher_slug) AS teacher_count
FROM tenants t JOIN public_classes pc ON pc.tenant_id = t.id
WHERE t.org_type = 'institute'
GROUP BY t.slug, t.name, t.logo_url;
CREATE VIEW public_subjects AS
SELECT s.id, s.slug, s.name, s.sort_order,
       (SELECT count(*) FROM public_classes pc WHERE pc.subject_id = s.id) AS class_count,
       (SELECT count(DISTINCT pc.teacher_slug) FROM public_classes pc WHERE pc.subject_id = s.id) AS teacher_count
FROM subjects s WHERE s.is_active;
-- ALTER VIEW public_classes, public_class_months, public_lessons, public_teachers, public_institutes,
-- public_subjects OWNER TO eduzone_admin; REVOKE ALL ... FROM PUBLIC; GRANT SELECT ... TO eduzone_app;
