"""Courses, step C5 (docs/COURSES.md sections C.7 and C.8): coupons and the wishlist.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-09

- coupons (tenant-scoped): a code for one course or every course of the organization, percent (basis points) or a
  fixed amount, optionally public (an automatic "sale price" shown on the course), with dates (at most 90 days,
  service rule), a redemption limit and an on/off switch. redeemed_count is counted when an order is paid.
- order_items gain list_price_cents, discount_cents and coupon_id: amount_cents stays the amount actually paid, and
  commission is charged on it (unchanged rule). cart_items gain coupon_code (a code the student typed).
- A coupon may make a course free: checkouts.total_cents and checkout_payments.amount_cents may now be 0 (a free
  checkout is fulfilled at once, without the gateway).
- public_courses gains sale_price_cents and sale_ends_at (the best public coupon right now).
- wishlist_items (platform-level, user policy like the cart): saved courses. wishlist_count(course) gives an
  instructor the number of saves and nothing about who (SECURITY DEFINER).
"""

import importlib.util
from pathlib import Path

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | None = None
depends_on: str | None = None


def _module(name: str):  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name))
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_SALE = """
LEFT JOIN LATERAL (
    SELECT GREATEST(0, c.one_time_price_cents - CASE WHEN k.discount_type = 'percent'
                                                     THEN (c.one_time_price_cents * k.percent_bps + 5000) / 10000
                                                     ELSE LEAST(k.amount_cents, c.one_time_price_cents) END)
               AS sale_price_cents,
           k.ends_at AS sale_ends_at
    FROM coupons k
    WHERE k.tenant_id = c.tenant_id AND (k.class_id = c.id OR k.class_id IS NULL) AND k.is_public
      AND k.status = 'active' AND now() >= k.starts_at AND now() < k.ends_at
      AND (k.max_redemptions IS NULL OR k.redeemed_count < k.max_redemptions)
      AND c.pricing_model = 'one_time' AND c.one_time_price_cents > 0
    ORDER BY 1 ASC, k.ends_at
    LIMIT 1
) sale ON true
WHERE c.kind = 'course' AND c.status = 'published'
"""


def _public_courses_with_sale(m0011) -> str:  # type: ignore[no-untyped-def]
    sql = dict(m0011._VIEWS)["public_courses"]
    sql = sql.replace("CREATE VIEW public_courses", "CREATE OR REPLACE VIEW public_courses")
    sql = sql.replace("|| tp.display_name || ' ' || coalesce(c.description, '')) AS search\n",
                      "|| tp.display_name || ' ' || coalesce(c.description, '')) AS search,\n"
                      "       sale.sale_price_cents, sale.sale_ends_at\n")
    assert "WHERE c.kind = 'course' AND c.status = 'published'" in sql
    return sql.replace("WHERE c.kind = 'course' AND c.status = 'published'\n", _SALE)


def upgrade() -> None:
    op.execute("""
        CREATE TABLE coupons (
            id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            tenant_id           uuid NOT NULL DEFAULT current_tenant_id() REFERENCES tenants(id) ON DELETE CASCADE,
            class_id            uuid,
            code                citext NOT NULL CHECK (code ~* '^[A-Z0-9-]{4,20}$'),
            discount_type       text NOT NULL CHECK (discount_type IN ('percent','fixed')),
            percent_bps         integer CHECK (percent_bps BETWEEN 1 AND 10000),
            amount_cents        bigint CHECK (amount_cents > 0),
            is_public           boolean NOT NULL DEFAULT false,
            max_redemptions     integer CHECK (max_redemptions > 0),
            redeemed_count      integer NOT NULL DEFAULT 0 CHECK (redeemed_count >= 0),
            starts_at           timestamptz NOT NULL DEFAULT now(),
            ends_at             timestamptz NOT NULL,
            status              text NOT NULL DEFAULT 'active' CHECK (status IN ('active','disabled')),
            created_by          uuid NOT NULL,
            created_at          timestamptz NOT NULL DEFAULT now(),
            UNIQUE (tenant_id, code),
            UNIQUE (tenant_id, id),
            FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id) ON DELETE CASCADE,
            FOREIGN KEY (tenant_id, created_by) REFERENCES tenant_members (tenant_id, id),
            CHECK ((discount_type = 'percent' AND percent_bps IS NOT NULL AND amount_cents IS NULL)
                OR (discount_type = 'fixed' AND amount_cents IS NOT NULL AND percent_bps IS NULL)),
            CHECK (ends_at > starts_at)
        )
    """)
    op.execute("CREATE INDEX idx_coupons_public ON coupons (tenant_id, class_id) WHERE is_public AND status = 'active'")
    op.execute("ALTER TABLE coupons ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE coupons FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY tenant_isolation ON coupons
                  USING (tenant_id = current_tenant_id()) WITH CHECK (tenant_id = current_tenant_id())""")
    op.execute("GRANT SELECT, INSERT, UPDATE ON coupons TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE ON coupons TO eduzone_admin")

    op.execute("""
        ALTER TABLE order_items
            ADD COLUMN list_price_cents bigint CHECK (list_price_cents >= 0),
            ADD COLUMN discount_cents   bigint NOT NULL DEFAULT 0 CHECK (discount_cents >= 0),
            ADD COLUMN coupon_id        uuid,
            ADD CONSTRAINT order_items_coupon_fk FOREIGN KEY (tenant_id, coupon_id) REFERENCES coupons (tenant_id, id)
    """)
    op.execute("ALTER TABLE cart_items ADD COLUMN coupon_code citext CHECK (coupon_code ~* '^[A-Z0-9-]{4,20}$')")
    op.execute("GRANT UPDATE (coupon_code) ON cart_items TO eduzone_app")

    op.execute("ALTER TABLE checkouts DROP CONSTRAINT checkouts_total_cents_check")
    op.execute("ALTER TABLE checkouts ADD CONSTRAINT checkouts_total_cents_check CHECK (total_cents >= 0)")
    op.execute("ALTER TABLE checkout_payments DROP CONSTRAINT checkout_payments_amount_cents_check")
    op.execute("ALTER TABLE checkout_payments ADD CONSTRAINT checkout_payments_amount_cents_check CHECK (amount_cents >= 0)")

    op.execute(_public_courses_with_sale(_module("0011_public_courses.py")))

    op.execute("""
        CREATE TABLE wishlist_items (
            id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            user_id     uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            tenant_id   uuid NOT NULL,
            class_id    uuid NOT NULL,
            created_at  timestamptz NOT NULL DEFAULT now(),
            UNIQUE (user_id, class_id),
            FOREIGN KEY (tenant_id, class_id) REFERENCES classes (tenant_id, id) ON DELETE CASCADE
        )
    """)
    op.execute("CREATE INDEX idx_wishlist_class ON wishlist_items (class_id)")
    op.execute("ALTER TABLE wishlist_items ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE wishlist_items FORCE ROW LEVEL SECURITY")
    op.execute("""CREATE POLICY wishlist_own ON wishlist_items
                  USING (user_id = current_user_id()) WITH CHECK (user_id = current_user_id())""")
    op.execute("GRANT SELECT, INSERT, DELETE ON wishlist_items TO eduzone_app")
    op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON wishlist_items TO eduzone_admin")

    op.execute("""
        CREATE FUNCTION wishlist_count(p_class uuid) RETURNS integer
        LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public, pg_temp AS $$
            SELECT count(*)::integer FROM wishlist_items WHERE class_id = p_class
        $$
    """)
    op.execute("ALTER FUNCTION wishlist_count(uuid) OWNER TO eduzone_admin")
    op.execute("REVOKE ALL ON FUNCTION wishlist_count(uuid) FROM PUBLIC")
    op.execute("GRANT EXECUTE ON FUNCTION wishlist_count(uuid) TO eduzone_app")


def downgrade() -> None:
    m0011, m0013 = _module("0011_public_courses.py"), _module("0013_reviews_certificates.py")
    op.execute("DROP FUNCTION wishlist_count(uuid)")
    op.execute("DROP TABLE wishlist_items")
    # public_courses loses its sale columns: rebuild it and the views on it as migrations 0011 and 0013 made them.
    for name in ("public_course_reviews", "public_instructors", "public_course_categories", "public_course_lectures",
                 "public_course_sections", "public_courses"):
        op.execute(f"DROP VIEW {name}")
    for name, sql in m0011._VIEWS:
        op.execute(sql)
        op.execute(f"ALTER VIEW {name} OWNER TO eduzone_admin")
        op.execute(f"GRANT SELECT ON {name} TO eduzone_app")
    source = Path(m0013.__file__).read_text(encoding="utf-8")
    view = source[source.index("CREATE VIEW public_course_reviews"):source.index("WHERE r.status = 'visible'")]
    op.execute(view + "WHERE r.status = 'visible'")
    op.execute("ALTER VIEW public_course_reviews OWNER TO eduzone_admin")
    op.execute("GRANT SELECT ON public_course_reviews TO eduzone_app")
    op.execute("DELETE FROM checkout_payments WHERE amount_cents = 0")
    op.execute("DELETE FROM checkouts WHERE total_cents = 0")
    op.execute("ALTER TABLE checkout_payments DROP CONSTRAINT checkout_payments_amount_cents_check")
    op.execute("ALTER TABLE checkout_payments ADD CONSTRAINT checkout_payments_amount_cents_check CHECK (amount_cents > 0)")
    op.execute("ALTER TABLE checkouts DROP CONSTRAINT checkouts_total_cents_check")
    op.execute("ALTER TABLE checkouts ADD CONSTRAINT checkouts_total_cents_check CHECK (total_cents > 0)")
    op.execute("ALTER TABLE cart_items DROP COLUMN coupon_code")
    op.execute("ALTER TABLE order_items DROP CONSTRAINT order_items_coupon_fk, DROP COLUMN coupon_id, "
               "DROP COLUMN discount_cents, DROP COLUMN list_price_cents")
    op.execute("DROP TABLE coupons")
