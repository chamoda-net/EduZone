"""The refund queue (step C6, docs/COURSES.md section 9): EduZone staff decide the refunds the automatic rule didn't
approve, retry ones the gateway refused, and record ones refunded by hand in the gateway's portal (PayHere until its
refund API is set up). Processing itself lives in app.modules.courses.refunds."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AdminSession
from app.core.errors import ApiError
from app.core.pagination import decode_cursor, encode_cursor
from app.modules.courses import refunds
from app.modules.platform.auth import PlatformActor
from app.modules.platform.service import _audit, _set_tenant

RefundFilter = Literal["open", "requested", "approved", "processed", "rejected", "all"]


class PlatformRefund(BaseModel):
    id: UUID
    status: str
    amount_cents: int
    currency: str
    reason: str
    auto_approved: bool
    decision_note: str | None
    failure_reason: str | None             # the last gateway attempt ("manual: ..." or "failed: ...")
    gateway_refund_ref: str | None
    created_at: datetime
    decided_at: datetime | None
    processed_at: datetime | None
    tenant_id: UUID
    tenant_name: str
    student_user_id: UUID
    student_name: str
    student_phone: str | None
    course_id: UUID
    course_title: str
    order_no: str
    paid_at: datetime | None


class PlatformRefundDetail(PlatformRefund):
    progress_percent: int                  # of the course, now
    in_window: bool                        # paid less than 7 days ago
    certificate: bool                      # an active certificate
    recent_refunds: int                    # the student's refunds (any organization) in the last 90 days
    gateway: str
    gateway_payment_ref: str | None


class PlatformRefundPage(BaseModel):
    items: list[PlatformRefund]
    next_cursor: str | None


class RefundDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=1000)


class ManualRefund(BaseModel):
    model_config = ConfigDict(extra="forbid")

    gateway_refund_ref: str = Field(min_length=2, max_length=120)


_SELECT = """
    SELECT r.id, r.status, r.amount_cents, o.currency, r.reason, r.auto_approved, r.decision_note, r.failure_reason,
           r.gateway_refund_ref, r.created_at, r.decided_at, r.processed_at, r.tenant_id, t.name AS tenant_name,
           u.id AS student_user_id, u.full_name AS student_name, u.phone AS student_phone, c.id AS course_id,
           c.title AS course_title, o.order_no, o.paid_at, r.requested_by
    FROM refunds r
    JOIN tenants t ON t.id = r.tenant_id
    JOIN order_items i ON i.id = r.order_item_id
    JOIN orders o ON o.id = i.order_id
    JOIN classes c ON c.id = i.class_id
    JOIN tenant_members tm ON tm.id = r.requested_by
    JOIN users u ON u.id = tm.user_id
"""


def _row(r: Any) -> PlatformRefund:
    return PlatformRefund.model_validate({k: getattr(r, k) for k in PlatformRefund.model_fields})


async def list_refunds(session: AsyncSession, *, status: RefundFilter, cursor: str | None,
                       limit: int) -> PlatformRefundPage:
    after = decode_cursor(cursor) if cursor else None
    statuses = {"open": ["requested", "approved"], "all": None}.get(status, [status])
    rows = (await session.execute(text(_SELECT + """
        WHERE (CAST(:st AS text[]) IS NULL OR r.status = ANY(CAST(:st AS text[])))
          AND (CAST(:after_ts AS timestamptz) IS NULL OR (r.created_at, r.id) < (:after_ts, :after_id))
        ORDER BY r.created_at DESC, r.id DESC LIMIT :limit
    """), {"st": statuses, "after_ts": after[0] if after else None, "after_id": after[1] if after else None,
           "limit": limit + 1})).all()
    page = rows[:limit]
    return PlatformRefundPage(items=[_row(r) for r in page],
                              next_cursor=encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None)


async def get_refund(session: AsyncSession, refund_id: UUID) -> PlatformRefundDetail:
    r = (await session.execute(text(_SELECT + " WHERE r.id = :id"), {"id": refund_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Refund not found.", status_code=404)
    extra = (await session.execute(text("""
        SELECT
          (SELECT CASE WHEN count(*) = 0 THEN 0
                       ELSE (count(*) FILTER (WHERE lc.lesson_id IS NOT NULL) * 100 / count(*)) END
           FROM lessons l
           LEFT JOIN lesson_completions lc ON lc.lesson_id = l.id AND lc.student_member_id = :m
           WHERE l.class_id = :c AND l.is_published AND l.section_id IS NOT NULL) AS progress_percent,
          EXISTS (SELECT 1 FROM certificates WHERE class_id = :c AND student_member_id = :m AND revoked_at IS NULL)
              AS certificate,
          (SELECT count(*) FROM refunds r2 JOIN tenant_members m2 ON m2.id = r2.requested_by
           WHERE m2.user_id = :u AND r2.status <> 'rejected' AND r2.created_at > now() - interval '90 days')
              AS recent_refunds,
          CAST(:paid AS timestamptz) > now() - interval '7 days' AS in_window
    """), {"m": r.requested_by, "c": r.course_id, "u": r.student_user_id, "paid": r.paid_at})).one()
    gateway, ref = await refunds.gateway_target(session, refund_id)
    return PlatformRefundDetail(**_row(r).model_dump(), progress_percent=int(extra.progress_percent),
                                certificate=extra.certificate, recent_refunds=int(extra.recent_refunds),
                                in_window=bool(extra.in_window),
                                gateway=gateway, gateway_payment_ref=ref)


@asynccontextmanager
async def _tenant_tx(tenant_id: UUID) -> AsyncIterator[AsyncSession]:
    """An eduzone_admin transaction pointed at one organization (for its ledger posting and audit rows)."""
    async with AdminSession() as session, session.begin():
        await _set_tenant(session, tenant_id)
        yield session


async def _locked(session: AsyncSession, refund_id: UUID) -> Any:
    r = (await session.execute(text("SELECT id, status, tenant_id FROM refunds WHERE id = :id FOR UPDATE"),
                               {"id": refund_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Refund not found.", status_code=404)
    return r


async def _process(actor: PlatformActor, refund_id: UUID, tenant_id: UUID) -> None:
    async with AdminSession() as session:
        gateway, ref = await refunds.gateway_target(session, refund_id)
    await refunds.execute(tenant_id, refund_id, gateway, ref, _tenant_tx, actor_user_id=actor.user_id)


async def decide(actor: PlatformActor, refund_id: UUID, body: RefundDecision) -> PlatformRefundDetail:
    note = (body.note or "").strip() or None
    if body.decision == "reject" and not note:
        raise ApiError("NOTE_REQUIRED", "Say why the refund is refused; the student sees it.", status_code=422)
    async with AdminSession() as session, session.begin():
        r = await _locked(session, refund_id)
        if r.status != "requested":
            raise ApiError("REFUND_NOT_REQUESTED", "This refund was already decided.", status_code=409)
        await _set_tenant(session, r.tenant_id)
        await session.execute(text("""
            UPDATE refunds SET status = :st, decided_by = :by, decided_at = now(), decision_note = :note WHERE id = :id
        """), {"st": "approved" if body.decision == "approve" else "rejected", "by": actor.user_id, "note": note,
               "id": refund_id})
        await _audit(session, actor, f"platform.refund.{body.decision}", "refund", refund_id, {"note": note})
    if body.decision == "approve":
        await _process(actor, refund_id, r.tenant_id)
    async with AdminSession() as session:
        return await get_refund(session, refund_id)


async def retry(actor: PlatformActor, refund_id: UUID) -> PlatformRefundDetail:
    async with AdminSession() as session:
        r = await _locked(session, refund_id)
    if r.status != "approved":
        raise ApiError("REFUND_NOT_APPROVED", "Only an approved refund waiting for the gateway can be retried.", 409)
    await _process(actor, refund_id, r.tenant_id)
    async with AdminSession() as session, session.begin():
        await _set_tenant(session, r.tenant_id)
        await _audit(session, actor, "platform.refund.retry", "refund", refund_id, None)
    async with AdminSession() as session:
        return await get_refund(session, refund_id)


async def mark_processed(actor: PlatformActor, refund_id: UUID, body: ManualRefund) -> PlatformRefundDetail:
    """Staff refunded it in the gateway's portal: record the gateway's reference and finish the refund here."""
    async with AdminSession() as session:
        r = await _locked(session, refund_id)
    if r.status != "approved":
        raise ApiError("REFUND_NOT_APPROVED", "Only an approved refund can be recorded as refunded.", status_code=409)
    async with _tenant_tx(r.tenant_id) as session:
        await refunds.finalize(session, refund_id, body.gateway_refund_ref.strip(), actor_user_id=actor.user_id)
        await _audit(session, actor, "platform.refund.manual", "refund", refund_id,
                     {"gateway_refund_ref": body.gateway_refund_ref.strip()})
    async with AdminSession() as session:
        return await get_refund(session, refund_id)
