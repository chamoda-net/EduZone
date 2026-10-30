"""Platform admin (build step 9, minimum): organizations and their owners, every payment,
balances and payouts, Bunny usage. Runs as eduzone_admin (BYPASSRLS); tenant-scoped writes
(owner member, payout ledger posting, audit rows) set app.tenant_id for that transaction so
rows carry the right tenant_id."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.errors import ApiError
from app.core.pagination import decode_cursor, encode_cursor
from app.modules.ledger import posting
from app.modules.platform.auth import PlatformActor
from app.modules.platform.schemas import (
    PayoutCreate,
    PayoutRow,
    PlatformPayment,
    PlatformPaymentPage,
    TenantCreate,
    TenantCreated,
    TenantRow,
    TenantUpdate,
)

_TENANT_SELECT = """
    SELECT t.id, t.name, t.slug, t.org_type, t.status, t.currency, t.commission_bps, t.gateway_fee_bearer,
           t.primary_color, t.logo_url, t.bunny_library_id, t.payout_bank_name, t.payout_account_masked,
           t.created_at, t.storage_limit_bytes, t.bandwidth_limit_bytes,
           (SELECT count(*) FROM tenant_members m WHERE m.tenant_id = t.id AND m.role <> 'student') AS members,
           (SELECT count(*) FROM tenant_members m WHERE m.tenant_id = t.id AND m.role = 'student') AS students,
           COALESCE((SELECT -sum(e.amount_cents) FROM ledger_entries e
                     WHERE e.tenant_id = t.id AND e.account = 'tenant_payable'), 0) AS balance_due_cents,
           COALESCE((SELECT c.gross_sales_cents FROM v_tenant_cashflow_monthly c
                     WHERE c.tenant_id = t.id
                       AND c.month = date_trunc('month', now() AT TIME ZONE 'Asia/Colombo')::date), 0)
               AS sales_this_month_cents,
           COALESCE((SELECT sum(a.size_bytes) FROM media_assets a
                     WHERE a.tenant_id = t.id AND a.status NOT IN ('deleted', 'failed')), 0) AS storage_used_bytes,
           COALESCE((SELECT sum(u.bandwidth_bytes) FROM tenant_usage_daily u
                     WHERE u.tenant_id = t.id
                       AND u.usage_date >= date_trunc('month', now() AT TIME ZONE 'Asia/Colombo')::date), 0)
               AS bandwidth_this_month_bytes,
           (SELECT max(u.usage_date) FROM tenant_usage_daily u WHERE u.tenant_id = t.id) AS usage_synced_on
    FROM tenants t
"""


def _tenant(r: Any) -> TenantRow:
    return TenantRow.model_validate({k: getattr(r, k) for k in TenantRow.model_fields})


async def _set_tenant(session: AsyncSession, tenant_id: UUID | None) -> None:
    """Make current_tenant_id() (used by inserts, audit rows and ledger posting) point at a tenant."""
    await session.execute(text("SELECT set_config('app.tenant_id', :t, true)"),
                          {"t": str(tenant_id) if tenant_id else ""})


async def _audit(session: AsyncSession, actor: PlatformActor, action: str, entity_type: str, entity_id: UUID,
                 details: dict[str, object] | None = None) -> None:
    await write_audit(session, actor_user_id=actor.user_id, action=action, entity_type=entity_type,
                      entity_id=entity_id, details=details, ip=actor.ip)


# --- organizations -----------------------------------------------------------------------

async def list_tenants(session: AsyncSession, *, status: str | None) -> list[TenantRow]:
    rows = (await session.execute(text(f"""
        {_TENANT_SELECT} WHERE (CAST(:st AS text) IS NULL OR t.status = :st) ORDER BY t.created_at DESC
    """), {"st": status})).all()
    return [_tenant(r) for r in rows]


async def get_tenant(session: AsyncSession, tenant_id: UUID) -> TenantRow:
    r = (await session.execute(text(f"{_TENANT_SELECT} WHERE t.id = :id"), {"id": tenant_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Organization not found.", status_code=404)
    return _tenant(r)


async def create_tenant(session: AsyncSession, actor: PlatformActor, body: TenantCreate) -> TenantCreated:
    if (await session.execute(text("SELECT 1 FROM tenants WHERE slug = :s"), {"s": body.slug})).first():
        raise ApiError("SLUG_TAKEN", "Another organization already uses this address.", status_code=409)
    if body.bunny_library_id is not None and (await session.execute(
            text("SELECT 1 FROM tenants WHERE bunny_library_id = :b"), {"b": body.bunny_library_id})).first():
        raise ApiError("LIBRARY_IN_USE", "That Bunny library belongs to another organization.", status_code=409)
    tenant_id = (await session.execute(text("""
        INSERT INTO tenants (name, slug, org_type, commission_bps, gateway_fee_bearer, primary_color,
                             bunny_library_id, storage_limit_bytes, bandwidth_limit_bytes)
        VALUES (:name, :slug, :org_type, :bps, :bearer, :color, :lib, :storage, :bandwidth)
        RETURNING id
    """), {"name": body.name, "slug": body.slug, "org_type": body.org_type, "bps": body.commission_bps,
           "bearer": body.gateway_fee_bearer, "color": body.primary_color, "lib": body.bunny_library_id,
           "storage": body.storage_limit_bytes, "bandwidth": body.bandwidth_limit_bytes})).scalar_one()

    # The owner: an existing person keeps their name; a new one is created.
    user_id = (await session.execute(text("""
        INSERT INTO users (email, full_name) VALUES (:e, :n)
        ON CONFLICT (email) DO UPDATE SET email = users.email
        RETURNING id
    """), {"e": body.owner_email, "n": body.owner_name})).scalar_one()
    await _set_tenant(session, tenant_id)
    member_id = (await session.execute(text("""
        INSERT INTO tenant_members (tenant_id, user_id, role, display_name)
        VALUES (:t, :u, 'owner', :n) RETURNING id
    """), {"t": tenant_id, "u": user_id, "n": body.owner_name})).scalar_one()
    await _audit(session, actor, "platform.tenant.create", "tenant", tenant_id,
                 {"slug": body.slug, "owner_email": body.owner_email})
    return TenantCreated(tenant=await get_tenant(session, tenant_id), owner_user_id=user_id, owner_member_id=member_id)


async def update_tenant(session: AsyncSession, actor: PlatformActor, tenant_id: UUID,
                        body: TenantUpdate) -> TenantRow:
    current = await get_tenant(session, tenant_id)
    changes = {k: v for k, v in body.changes().items() if getattr(current, k) != v}
    if changes:
        sets = ", ".join(f"{k} = :{k}" for k in changes)
        try:
            async with session.begin_nested():
                await session.execute(text(f"UPDATE tenants SET {sets} WHERE id = :id"), {**changes, "id": tenant_id})
        except IntegrityError as exc:
            raise ApiError("LIBRARY_IN_USE", "That Bunny library belongs to another organization.", 409) from exc
        await _set_tenant(session, tenant_id)
        action = "platform.tenant.suspend" if changes.get("status") == "suspended" else "platform.tenant.update"
        await _audit(session, actor, action, "tenant", tenant_id, {"changes": changes})
    return await get_tenant(session, tenant_id)


# --- payments ------------------------------------------------------------------------------

async def list_payments(session: AsyncSession, *, tenant_id: UUID | None, status: str | None,
                        cursor: str | None, limit: int) -> PlatformPaymentPage:
    after = decode_cursor(cursor) if cursor else None
    rows = (await session.execute(text("""
        SELECT o.id AS order_id, o.order_no, o.status, o.tenant_id, t.name AS tenant_name,
               u.full_name AS student_name, u.phone AS student_phone, i.description, o.total_cents, o.currency,
               p.gateway, p.gateway_payment_ref, o.created_at, o.paid_at
        FROM orders o
        JOIN tenants t ON t.id = o.tenant_id
        JOIN order_items i ON i.order_id = o.id
        JOIN tenant_members tm ON tm.id = o.student_member_id
        JOIN users u ON u.id = tm.user_id
        LEFT JOIN LATERAL (SELECT gateway, gateway_payment_ref FROM payments p WHERE p.order_id = o.id
                           ORDER BY (p.status = 'succeeded') DESC, p.created_at DESC LIMIT 1) p ON true
        WHERE (CAST(:tid AS uuid) IS NULL OR o.tenant_id = :tid)
          AND (CAST(:st AS text) IS NULL OR o.status = :st)
          AND (CAST(:after_ts AS timestamptz) IS NULL OR (o.created_at, o.id) < (:after_ts, :after_id))
        ORDER BY o.created_at DESC, o.id DESC
        LIMIT :limit
    """), {"tid": tenant_id, "st": status, "after_ts": after[0] if after else None,
           "after_id": after[1] if after else None, "limit": limit + 1})).all()
    page = rows[:limit]
    return PlatformPaymentPage(
        items=[PlatformPayment.model_validate({k: getattr(r, k) for k in PlatformPayment.model_fields}) for r in page],
        next_cursor=encode_cursor(page[-1].created_at, page[-1].order_id) if len(rows) > limit else None,
    )


# --- payouts -------------------------------------------------------------------------------

_PAYOUT_SELECT = """
    SELECT p.id, p.tenant_id, p.amount_cents, p.period_start, p.period_end, p.status, p.bank_reference,
           u.full_name AS created_by_name, p.sent_at, p.created_at
    FROM payouts p LEFT JOIN users u ON u.id = p.created_by
"""


async def list_payouts(session: AsyncSession, tenant_id: UUID) -> list[PayoutRow]:
    rows = (await session.execute(text(f"{_PAYOUT_SELECT} WHERE p.tenant_id = :t ORDER BY p.created_at DESC"),
                                  {"t": tenant_id})).all()
    return [PayoutRow.model_validate({k: getattr(r, k) for k in PayoutRow.model_fields}) for r in rows]


async def record_payout(session: AsyncSession, actor: PlatformActor, tenant_id: UUID,
                        body: PayoutCreate) -> PayoutRow:
    """Money already sent to the organization's bank: a payouts row and its ledger posting
    (tenant_payable +X, bank -X) in one transaction. Never more than the balance due."""
    locked = (await session.execute(text("SELECT id FROM tenants WHERE id = :t FOR UPDATE"),
                                    {"t": tenant_id})).one_or_none()
    if locked is None:
        raise ApiError("NOT_FOUND", "Organization not found.", status_code=404)
    balance = (await session.execute(text("""
        SELECT COALESCE(-sum(amount_cents), 0) FROM ledger_entries WHERE tenant_id = :t AND account = 'tenant_payable'
    """), {"t": tenant_id})).scalar_one()
    if body.amount_cents > balance:
        raise ApiError("PAYOUT_EXCEEDS_BALANCE",
                       f"The balance due is {balance} cents; a payout can't be larger.", status_code=409)
    await _set_tenant(session, tenant_id)
    payout_id = (await session.execute(text("""
        INSERT INTO payouts (tenant_id, amount_cents, period_start, period_end, status, bank_reference,
                             created_by, sent_at)
        VALUES (:t, :amt, :ps, :pe, 'sent', :ref, :by, now()) RETURNING id
    """), {"t": tenant_id, "amt": body.amount_cents, "ps": body.period_start, "pe": body.period_end,
           "ref": body.bank_reference, "by": actor.user_id})).scalar_one()
    await posting.post(session, kind="payout", entries=posting.payout_entries(body.amount_cents),
                       payout_id=payout_id, created_by=actor.user_id, memo=body.bank_reference)
    await _audit(session, actor, "platform.payout.create", "payout", payout_id,
                 {"amount_cents": body.amount_cents, "bank_reference": body.bank_reference})
    r = (await session.execute(text(f"{_PAYOUT_SELECT} WHERE p.id = :id"), {"id": payout_id})).one()
    return PayoutRow.model_validate({k: getattr(r, k) for k in PayoutRow.model_fields})
