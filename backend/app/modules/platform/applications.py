"""Reviewing teacher applications (migration phase 5). Runs as eduzone_admin like the rest of the platform admin.

approve → the organization becomes active and gets the payout display fields; request_changes → the applicant
edits and resubmits; reject → the organization is closed. Opening the document and revealing the account
number are audited too: they are the most sensitive things EduZone stores about a teacher.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.errors import ApiError
from app.integrations.private_storage import PrivateStorage
from app.modules.onboarding.schemas import (
    AccountNumber,
    ApplicationDetail,
    ApplicationRow,
    ApplicationStatus,
    DecisionIn,
    SubjectRef,
)
from app.modules.onboarding.service import APPLICATION_SELECT
from app.modules.platform.auth import PlatformActor
from app.modules.platform.service import _audit, _set_tenant

_DETAIL_SELECT = APPLICATION_SELECT.replace("SELECT a.*,", """
    SELECT a.*, u.full_name AS applicant_name, u.email AS applicant_email, u.phone AS applicant_phone,
           rv.full_name AS reviewed_by_name,""").replace("JOIN tenants t ON t.id = a.tenant_id", """
    JOIN tenants t ON t.id = a.tenant_id
    JOIN users u ON u.id = a.user_id
    LEFT JOIN users rv ON rv.id = a.reviewed_by""")

# What each decision needs and does.
_FROM = {"approve": ("submitted",), "request_changes": ("submitted",), "reject": ("submitted", "changes_requested")}
_TO = {"approve": ("approved", "active"), "request_changes": ("changes_requested", None), "reject": ("rejected", "closed")}


async def list_applications(session: AsyncSession, status: ApplicationStatus | None) -> list[ApplicationRow]:
    rows = (await session.execute(text(_DETAIL_SELECT + """
        WHERE CAST(:st AS text) IS NULL OR a.status = :st
        ORDER BY (a.status = 'submitted') DESC, a.submitted_at
    """), {"st": status})).all()
    return [ApplicationRow.model_validate({k: getattr(r, k) for k in ApplicationRow.model_fields}) for r in rows]


async def _load(session: AsyncSession, application_id: UUID, *, for_update: bool = False) -> Any:
    row = (await session.execute(text(_DETAIL_SELECT + " WHERE a.id = :id" + (" FOR UPDATE OF a" if for_update else "")),
                                 {"id": application_id})).one_or_none()
    if row is None:
        raise ApiError("NOT_FOUND", "Application not found.", status_code=404)
    return row


def _detail(r: Any) -> ApplicationDetail:
    fields = {k: getattr(r, k) for k in ApplicationDetail.model_fields if k != "subjects"}
    return ApplicationDetail(**fields, subjects=[SubjectRef(**s) for s in r.subjects])


async def get_application(session: AsyncSession, application_id: UUID) -> ApplicationDetail:
    return _detail(await _load(session, application_id))


async def document(session: AsyncSession, actor: PlatformActor, storage: PrivateStorage,
                   application_id: UUID) -> tuple[bytes, str, str]:
    r = await _load(session, application_id)
    content = await storage.get(r.document_key)
    await _set_tenant(session, r.tenant_id)
    await _audit(session, actor, "platform.application.document", "teacher_application", r.id)
    return content, r.document_type, r.document_name


async def reveal_account(session: AsyncSession, actor: PlatformActor, application_id: UUID) -> AccountNumber:
    r = await _load(session, application_id)
    await _set_tenant(session, r.tenant_id)
    await _audit(session, actor, "platform.application.reveal_account", "teacher_application", r.id)
    return AccountNumber(account_number=crypto.decrypt(r.payout_account_enc))


async def decide(session: AsyncSession, actor: PlatformActor, application_id: UUID,
                 body: DecisionIn) -> ApplicationDetail:
    r = await _load(session, application_id, for_update=True)
    if r.status not in _FROM[body.decision]:
        raise ApiError("APPLICATION_STATUS", f"A {r.status.replace('_', ' ')} application can't be changed this way.",
                       status_code=409)
    note = (body.note or "").strip() or None
    if body.decision != "approve" and note is None:
        raise ApiError("NOTE_REQUIRED", "Tell the applicant what to change, or why it was rejected.", status_code=422)
    status, tenant_status = _TO[body.decision]
    await session.execute(text("""
        UPDATE teacher_applications SET status = :st, review_note = :note, reviewed_by = :by, reviewed_at = now()
        WHERE id = :id
    """), {"st": status, "note": note, "by": actor.user_id, "id": r.id})
    if body.decision == "approve":
        await session.execute(text("""
            UPDATE tenants SET status = 'active', payout_bank_name = :bank, payout_account_masked = :masked
            WHERE id = :t
        """), {"bank": r.payout_bank_name, "masked": r.payout_account_masked, "t": r.tenant_id})
    elif tenant_status is not None:
        await session.execute(text("UPDATE tenants SET status = :s WHERE id = :t"),
                              {"s": tenant_status, "t": r.tenant_id})
    await _set_tenant(session, r.tenant_id)
    await _audit(session, actor, f"platform.application.{body.decision}", "teacher_application", r.id,
                 {"note": note, "org_name": r.org_name})
    return _detail(await _load(session, application_id))
