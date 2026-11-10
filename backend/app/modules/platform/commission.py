"""Commission rates and scheduled changes (step C7, docs/COURSES.md C.10).

Rates are per product type (tuition, course): the platform default, or an organization's override. Nothing changes
at once: every change is scheduled, announced to the owners it affects (email, and a banner on their Money page),
and takes effect on its date. An increase needs COMMISSION_NOTICE_DAYS (30) of notice; a decrease may come sooner.
Checkout reads the rate through commission_rate() (migration 0016), which already counts changes whose time has come,
so applying them (`apply_due`) only records it. Sales keep the rate snapshotted on their order item.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.errors import ApiError
from app.integrations.email import get_email_sender
from app.modules.platform.auth import PlatformActor
from app.modules.platform.service import _audit, _set_tenant

log = logging.getLogger("eduzone.commission")

Kind = Literal["tuition", "course"]


class PlatformRate(BaseModel):
    kind: str
    commission_bps: int                   # the default now (due changes included)
    updated_at: datetime


class NotifiedTenant(BaseModel):
    tenant_id: UUID
    tenant_name: str
    emails: list[str]


class CommissionChange(BaseModel):
    id: UUID
    scope: str                            # platform | tenant
    tenant_id: UUID | None
    tenant_name: str | None
    kind: str
    old_bps: int
    new_bps: int
    reason: str
    announced_at: datetime
    effective_at: datetime
    status: str                           # scheduled | applied | cancelled
    applied_at: datetime | None
    cancelled_at: datetime | None
    notified: list[NotifiedTenant]
    created_by_name: str


class CommissionOverview(BaseModel):
    notice_days: int
    rates: list[PlatformRate]
    changes: list[CommissionChange]       # scheduled first (soonest first), then the latest 50 others


class ChangeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: Literal["platform", "tenant"]
    tenant_id: UUID | None = None
    kind: Kind
    new_bps: int = Field(ge=0, le=10000)
    effective_at: AwareDatetime
    reason: str = Field(min_length=3, max_length=1000)


_SELECT = """
    SELECT c.id, c.scope, c.tenant_id, t.name AS tenant_name, c.kind, c.old_bps, c.new_bps, c.reason, c.announced_at,
           c.effective_at, c.status, c.applied_at, c.cancelled_at, c.notified, u.full_name AS created_by_name
    FROM commission_changes c
    LEFT JOIN tenants t ON t.id = c.tenant_id
    JOIN users u ON u.id = c.created_by
"""


def _change(r: Any) -> CommissionChange:
    return CommissionChange.model_validate(dict(r._mapping))


def _pct(bps: int) -> str:
    return f"{bps / 100:g}%"


async def apply_due(session: AsyncSession) -> int:
    """Record the changes whose date has come: the default or the override takes the new rate. In an eduzone_admin
    transaction; safe to run any time (the admin pages call it; a daily job may too)."""
    due = (await session.execute(text("""
        SELECT id, scope, tenant_id, kind, new_bps FROM commission_changes
        WHERE status = 'scheduled' AND effective_at <= now() ORDER BY effective_at FOR UPDATE SKIP LOCKED
    """))).all()
    for c in due:
        if c.scope == "platform":
            await session.execute(text("""
                UPDATE platform_commission_rates SET commission_bps = :bps, updated_at = now() WHERE kind = :k
            """), {"bps": c.new_bps, "k": c.kind})
        else:
            column = "course_commission_bps" if c.kind == "course" else "tuition_commission_bps"
            await session.execute(text(f"UPDATE tenants SET {column} = :bps WHERE id = :t"),
                                  {"bps": c.new_bps, "t": c.tenant_id})
        await session.execute(text(
            "UPDATE commission_changes SET status = 'applied', applied_at = now() WHERE id = :id"), {"id": c.id})
        await _set_tenant(session, c.tenant_id)
        await write_audit(session, actor_user_id=None, action="commission.applied", entity_type="commission_change",
                          entity_id=c.id, details={"scope": c.scope, "kind": c.kind, "new_bps": c.new_bps})
    await _set_tenant(session, None)
    return len(due)


async def overview(session: AsyncSession) -> CommissionOverview:
    await apply_due(session)
    rates = (await session.execute(text(
        "SELECT kind, commission_bps, updated_at FROM platform_commission_rates ORDER BY kind DESC"))).all()
    scheduled = (await session.execute(text(_SELECT + " WHERE c.status = 'scheduled' ORDER BY c.effective_at"))).all()
    others = (await session.execute(text(_SELECT + """
        WHERE c.status <> 'scheduled' ORDER BY c.created_at DESC LIMIT 50
    """))).all()
    return CommissionOverview(notice_days=get_settings().commission_notice_days,
                              rates=[PlatformRate.model_validate(dict(r._mapping)) for r in rates],
                              changes=[_change(r) for r in [*scheduled, *others]])


async def _affected(session: AsyncSession, scope: str, tenant_id: UUID | None, kind: str) -> list[NotifiedTenant]:
    """Whose rate this changes: the one organization, or (platform-wide) every active one without its own rate."""
    column = "course_commission_bps" if kind == "course" else "tuition_commission_bps"
    rows = (await session.execute(text(f"""
        SELECT t.id AS tenant_id, t.name AS tenant_name,
               COALESCE(array_agg(u.email ORDER BY u.email) FILTER (WHERE u.email IS NOT NULL), '{{}}') AS emails
        FROM tenants t
        LEFT JOIN tenant_members m ON m.tenant_id = t.id AND m.role = 'owner' AND m.status = 'active'
        LEFT JOIN users u ON u.id = m.user_id
        WHERE t.status IN ('active', 'pending')
          AND (CAST(:t AS uuid) IS NULL OR t.id = :t)
          AND (:scope = 'tenant' OR t.{column} IS NULL)
        GROUP BY t.id, t.name ORDER BY t.name
    """), {"t": tenant_id, "scope": scope})).all()
    return [NotifiedTenant(tenant_id=r.tenant_id, tenant_name=r.tenant_name, emails=list(r.emails)) for r in rows]


async def _notify(tenants: list[NotifiedTenant], subject: str, body: str) -> None:
    sender = get_email_sender()
    for tenant in tenants:
        for email in tenant.emails:
            try:
                await sender.send(email, subject, body.replace("{org}", tenant.tenant_name))
            except Exception:  # one bad address must not stop the others
                log.exception("commission notice to %s failed", email)


async def schedule(session: AsyncSession, actor: PlatformActor, body: ChangeCreate) -> CommissionChange:
    s = get_settings()
    await apply_due(session)
    if body.scope == "tenant":
        if body.tenant_id is None:
            raise ApiError("TENANT_REQUIRED", "Choose the organization.", status_code=422)
        if (await session.execute(text("SELECT 1 FROM tenants WHERE id = :t"), {"t": body.tenant_id})).first() is None:
            raise ApiError("NOT_FOUND", "Organization not found.", status_code=404)
        old = (await session.execute(text("SELECT commission_rate_for(:t, :k)"),
                                     {"t": body.tenant_id, "k": body.kind})).scalar_one()
    else:
        if body.tenant_id is not None:
            raise ApiError("TENANT_NOT_ALLOWED", "A platform-wide change has no organization.", status_code=422)
        old = (await session.execute(text("SELECT commission_bps FROM platform_commission_rates WHERE kind = :k"),
                                     {"k": body.kind})).scalar_one()
    now = datetime.now(UTC)
    if body.new_bps == old:
        raise ApiError("COMMISSION_UNCHANGED", "That is already the rate.", status_code=422)
    if body.effective_at <= now:
        raise ApiError("COMMISSION_DATE_PAST", "Choose a date in the future: changes are never immediate.", 422)
    notice = timedelta(days=s.commission_notice_days)
    if body.new_bps > old and body.effective_at < now + notice:
        raise ApiError("COMMISSION_NOTICE_TOO_SHORT",
                       f"An increase needs at least {s.commission_notice_days} days' notice.", status_code=422)
    tenants = await _affected(session, body.scope, body.tenant_id, body.kind)
    try:
        async with session.begin_nested():
            change_id = (await session.execute(text("""
                INSERT INTO commission_changes (scope, tenant_id, kind, old_bps, new_bps, reason, effective_at, notified,
                                                created_by)
                VALUES (:scope, :t, :k, :old, :new, :why, :at, CAST(:notified AS jsonb), :by) RETURNING id
            """), {"scope": body.scope, "t": body.tenant_id, "k": body.kind, "old": old, "new": body.new_bps,
                   "why": body.reason.strip(), "at": body.effective_at, "by": actor.user_id,
                   "notified": "[" + ",".join(x.model_dump_json() for x in tenants) + "]"})).scalar_one()
    except IntegrityError as exc:
        raise ApiError("COMMISSION_CHANGE_PENDING",
                       "A change for this rate is already scheduled; cancel it first.", status_code=409) from exc
    await _set_tenant(session, body.tenant_id)
    await _audit(session, actor, "platform.commission.schedule", "commission_change", change_id,
                 {"scope": body.scope, "kind": body.kind, "old_bps": old, "new_bps": body.new_bps,
                  "effective_at": body.effective_at.isoformat(), "notified": len(tenants)})
    await _set_tenant(session, None)
    product = "courses" if body.kind == "course" else "tuition classes"
    await _notify(tenants, f"EduZone commission on {product} changes on {body.effective_at:%d %B %Y}",
                  f"Hello {{org}},\n\nEduZone's commission on your {product} will change from {_pct(old)} to "
                  f"{_pct(body.new_bps)} on {body.effective_at:%d %B %Y}.\n\nWhy: {body.reason.strip()}\n\n"
                  "Sales made before that date keep the rate they were sold at. You can see this on the Money page "
                  "of your console.\n\nEduZone")
    r = (await session.execute(text(_SELECT + " WHERE c.id = :id"), {"id": change_id})).one()
    return _change(r)


async def cancel(session: AsyncSession, actor: PlatformActor, change_id: UUID) -> CommissionChange:
    r = (await session.execute(text(_SELECT + " WHERE c.id = :id FOR UPDATE OF c"), {"id": change_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Change not found.", status_code=404)
    if r.status != "scheduled" or r.effective_at <= datetime.now(UTC):
        raise ApiError("COMMISSION_NOT_CANCELLABLE", "Only a change that hasn't taken effect can be cancelled.", 409)
    await session.execute(text("""
        UPDATE commission_changes SET status = 'cancelled', cancelled_at = now(), cancelled_by = :by WHERE id = :id
    """), {"id": change_id, "by": actor.user_id})
    await _set_tenant(session, r.tenant_id)
    await _audit(session, actor, "platform.commission.cancel", "commission_change", change_id, None)
    await _set_tenant(session, None)
    change = _change(r)
    product = "courses" if r.kind == "course" else "tuition classes"
    await _notify(change.notified, f"EduZone commission change on {product} cancelled",
                  f"Hello {{org}},\n\nThe change of EduZone's commission on your {product} from {_pct(r.old_bps)} to "
                  f"{_pct(r.new_bps)}, announced for {r.effective_at:%d %B %Y}, is cancelled. Your rate stays "
                  f"{_pct(r.old_bps)}.\n\nEduZone")
    r = (await session.execute(text(_SELECT + " WHERE c.id = :id"), {"id": change_id})).one()
    return _change(r)
