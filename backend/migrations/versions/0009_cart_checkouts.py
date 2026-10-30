"""Cart and one payment across teachers (migration phase 6).

Revision ID: 0009
Revises: 0008
Create Date: 2026-10-30

- cart_items (platform-level, per user): a month or a one-time class of any teacher.
- checkouts + checkout_payments (platform-level): one gateway payment for several orders. Each order still has
  exactly one item and lives in its own tenant (orders.checkout_id); its `payments` row carries its share of the
  amount and of the gateway fee (payments.checkout_payment_id) so the ledger stays per tenant, per payment.
- All three are guarded by user policies (the app role sees only app.user_id's rows), like teacher_applications.
- resolve_checkout_payment(gateway, key): the webhook's lookup (no user yet), SECURITY DEFINER.
"""

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE cart_items (
            id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id        uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            class_id       uuid NOT NULL REFERENCES classes(id) ON DELETE CASCADE,
            class_month_id uuid REFERENCES class_months(id) ON DELETE CASCADE,
            created_at     timestamptz NOT NULL DEFAULT now(),
            UNIQUE NULLS NOT DISTINCT (user_id, class_id, class_month_id)
        )
    """)
    op.execute("CREATE INDEX idx_cart_items_user ON cart_items (user_id, created_at)")

    op.execute("""
        CREATE TABLE checkouts (
            id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            checkout_no  text NOT NULL UNIQUE,                 -- e.g. EZC-2610-3F9A1C
            status       text NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending', 'paid', 'failed', 'cancelled')),
            currency     char(3) NOT NULL,
            total_cents  bigint NOT NULL CHECK (total_cents > 0),
            paid_at      timestamptz,
            created_at   timestamptz NOT NULL DEFAULT now(),
            updated_at   timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute("CREATE INDEX idx_checkouts_user ON checkouts (user_id, created_at DESC)")
    op.execute("""
        CREATE TRIGGER trg_checkouts_updated BEFORE UPDATE ON checkouts
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)
    op.execute("""
        CREATE TABLE checkout_payments (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            checkout_id         uuid NOT NULL REFERENCES checkouts(id) ON DELETE CASCADE,
            gateway             text NOT NULL,
            idempotency_key     text NOT NULL UNIQUE,          -- sent to the gateway as its order id
            gateway_payment_ref text,
            amount_cents        bigint NOT NULL CHECK (amount_cents > 0),
            gateway_fee_cents   bigint CHECK (gateway_fee_cents >= 0),  -- estimate, split across the orders
            status              text NOT NULL DEFAULT 'initiated'
                                CHECK (status IN ('initiated', 'succeeded', 'failed', 'cancelled')),
            method              text,
            card_last4          char(4),
            failure_reason      text,
            created_at          timestamptz NOT NULL DEFAULT now(),
            updated_at          timestamptz NOT NULL DEFAULT now(),
            UNIQUE (gateway, gateway_payment_ref)
        )
    """)
    op.execute("CREATE INDEX idx_checkout_payments_checkout ON checkout_payments (checkout_id)")
    op.execute("""
        CREATE TRIGGER trg_checkout_payments_updated BEFORE UPDATE ON checkout_payments
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)
    op.execute("ALTER TABLE orders ADD COLUMN checkout_id uuid REFERENCES checkouts(id)")
    op.execute("CREATE INDEX idx_orders_checkout ON orders (checkout_id) WHERE checkout_id IS NOT NULL")
    op.execute("ALTER TABLE payments ADD COLUMN checkout_payment_id uuid REFERENCES checkout_payments(id)")
    op.execute("CREATE INDEX idx_payments_checkout_payment ON payments (checkout_payment_id) "
               "WHERE checkout_payment_id IS NOT NULL")

    # User policies: the app role sees and changes only the signed-in user's rows (app.user_id).
    for table in ("cart_items", "checkouts", "checkout_payments"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY cart_own ON cart_items
            USING (user_id = current_user_id()) WITH CHECK (user_id = current_user_id())
    """)
    op.execute("""
        CREATE POLICY checkout_own ON checkouts
            USING (user_id = current_user_id()) WITH CHECK (user_id = current_user_id())
    """)
    op.execute("""
        CREATE POLICY checkout_payment_own ON checkout_payments
            USING (checkout_id IN (SELECT id FROM checkouts WHERE user_id = current_user_id()))
            WITH CHECK (checkout_id IN (SELECT id FROM checkouts WHERE user_id = current_user_id()))
    """)
    op.execute("GRANT SELECT, INSERT, DELETE ON cart_items TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON checkouts, checkout_payments TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON cart_items TO eduzone_admin")
    op.execute("GRANT SELECT, INSERT, UPDATE ON checkouts, checkout_payments TO eduzone_admin")

    # The webhook arrives with no user: which checkout payment (and whose) a gateway key belongs to.
    op.execute("""
        CREATE FUNCTION resolve_checkout_payment(p_gateway text, p_key text)
        RETURNS TABLE (id uuid, checkout_id uuid, user_id uuid)
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
            SELECT cp.id, cp.checkout_id, c.user_id
            FROM checkout_payments cp JOIN checkouts c ON c.id = cp.checkout_id
            WHERE cp.gateway = p_gateway AND cp.idempotency_key = p_key
        $$
    """)
    op.execute("ALTER FUNCTION resolve_checkout_payment(text, text) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION resolve_checkout_payment(text, text) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION resolve_checkout_payment(text, text) TO eduzone_app")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS resolve_checkout_payment(text, text)")
    op.execute("ALTER TABLE payments DROP COLUMN checkout_payment_id")
    op.execute("ALTER TABLE orders DROP COLUMN checkout_id")
    op.execute("DROP TABLE checkout_payments")
    op.execute("DROP TABLE checkouts")
    op.execute("DROP TABLE cart_items")
