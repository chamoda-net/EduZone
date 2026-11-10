"""Courses, step C6 (docs/COURSES.md section 9): refunds.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-10

- refunds (in the baseline, unused until now) gain the decision trail: auto_approved, decided_by (an EduZone staff
  user), decided_at, decision_note, failure_reason (the last gateway attempt), updated_at. One open refund per order
  item (any status but rejected). Students read their own refunds (user policy, like orders), which also counts
  their recent refunds across organizations for the abuse rule.
- order_items.refunded_at: set when the refund is processed (the app may update only that column).
- v_tenant_pending_balance (security_invoker): the organization's net from course sales paid in the last 7 days and
  not refunded. A payout may not include it (the refund window): available = balance due - pending.
"""

from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | None = None
depends_on: str | None = None

_OWN_MEMBERS = "SELECT id FROM tenant_members WHERE user_id = current_user_id()"


def upgrade() -> None:
    op.execute("""
        ALTER TABLE refunds
            ADD COLUMN auto_approved  boolean NOT NULL DEFAULT false,
            ADD COLUMN decided_by     uuid REFERENCES users(id),
            ADD COLUMN decided_at     timestamptz,
            ADD COLUMN decision_note  text CHECK (char_length(decision_note) <= 1000),
            ADD COLUMN failure_reason text CHECK (char_length(failure_reason) <= 500),
            ADD COLUMN updated_at     timestamptz NOT NULL DEFAULT now(),
            ADD CONSTRAINT refunds_reason_length CHECK (char_length(reason) <= 1000)
    """)
    op.execute("CREATE TRIGGER trg_refunds_updated BEFORE UPDATE ON refunds FOR EACH ROW EXECUTE FUNCTION set_updated_at()")
    op.execute("CREATE UNIQUE INDEX uq_refund_open_item ON refunds (order_item_id) WHERE status <> 'rejected'")
    op.execute("CREATE INDEX idx_refunds_status ON refunds (status, created_at DESC)")
    op.execute(f"""
        CREATE POLICY user_own_rows ON refunds FOR SELECT
            USING (requested_by IN ({_OWN_MEMBERS}))
    """)

    op.execute("ALTER TABLE order_items ADD COLUMN refunded_at timestamptz")
    op.execute("GRANT UPDATE (refunded_at) ON order_items TO eduzone_app")

    op.execute("""
        CREATE VIEW v_tenant_pending_balance WITH (security_invoker = true) AS
        SELECT le.tenant_id, -SUM(le.amount_cents) AS pending_cents
        FROM ledger_entries le
        JOIN ledger_transactions lt ON lt.id = le.ledger_tx_id AND lt.kind = 'sale'
        JOIN order_items i ON i.id = le.order_item_id AND i.refunded_at IS NULL
        JOIN orders o ON o.id = i.order_id AND o.paid_at > now() - interval '7 days'
        JOIN classes c ON c.id = i.class_id AND c.kind = 'course'
        WHERE le.account = 'tenant_payable'
        GROUP BY le.tenant_id
    """)
    op.execute("GRANT SELECT ON v_tenant_pending_balance TO eduzone_app, eduzone_admin")


def downgrade() -> None:
    op.execute("DROP VIEW v_tenant_pending_balance")
    op.execute("REVOKE UPDATE (refunded_at) ON order_items FROM eduzone_app")
    op.execute("ALTER TABLE order_items DROP COLUMN refunded_at")
    op.execute("DROP POLICY user_own_rows ON refunds")
    op.execute("DROP INDEX idx_refunds_status")
    op.execute("DROP INDEX uq_refund_open_item")
    op.execute("DROP TRIGGER trg_refunds_updated ON refunds")
    op.execute("""
        ALTER TABLE refunds DROP CONSTRAINT refunds_reason_length, DROP COLUMN updated_at, DROP COLUMN failure_reason,
            DROP COLUMN decision_note, DROP COLUMN decided_at, DROP COLUMN decided_by, DROP COLUMN auto_approved
    """)
