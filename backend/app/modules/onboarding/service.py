"""Teacher self-registration (migration phase 5, CLAUDE.md section 2).

Applying opens a `pending` organization with the applicant as owner, a teacher profile and the application.
While pending, the console works in draft mode (nothing public, nothing published or sold). EduZone reviews
the application on the platform admin (`app.modules.platform.applications`). The ID or business document goes
to private storage; the bank account number is stored encrypted, with a masked copy for display.

teacher_applications is platform-level; its RLS policy shows the app role only the rows of app.user_id.
"""

import re
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import crypto
from app.core.audit import write_audit
from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError
from app.integrations.private_storage import PrivateStorage
from app.modules.market import profiles
from app.modules.onboarding.schemas import ApplicationFields, ApplicationOut, SubjectRef
from app.modules.platform.schemas import RESERVED_SLUGS

MAX_DOCUMENT_BYTES = 10 * 1024 * 1024
# Magic bytes → (content type, extension). Phones send photos; offices send PDFs.
_DOCUMENT_TYPES = (
    (b"%PDF-", "application/pdf", "pdf"),
    (b"\xff\xd8\xff", "image/jpeg", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", "png"),
)
OPEN_STATUSES = ("submitted", "changes_requested")

# Used by the applicant (user transaction: the tenants join shows only their own organizations) and by
# the platform admin (eduzone_admin sees every row).
APPLICATION_SELECT = """
    SELECT a.*, t.slug AS tenant_slug,
           COALESCE((SELECT json_agg(json_build_object('id', s.id, 'name', s.name) ORDER BY s.sort_order, s.name)
                     FROM subjects s WHERE s.id = ANY (a.subject_ids)), '[]') AS subjects
    FROM teacher_applications a JOIN tenants t ON t.id = a.tenant_id
"""


@dataclass(frozen=True, slots=True)
class Document:
    name: str
    content: bytes


def check_document(doc: Document) -> tuple[str, str, str]:
    """→ (content type, extension, safe display name). A PDF, JPEG or PNG up to 10 MB, checked by its bytes."""
    if not doc.content:
        raise ApiError("DOCUMENT_REQUIRED", "Attach your ID or business registration document.", status_code=422)
    if len(doc.content) > MAX_DOCUMENT_BYTES:
        raise ApiError("DOCUMENT_TOO_LARGE", "The document must be 10 MB or smaller.", status_code=413)
    for magic, content_type, ext in _DOCUMENT_TYPES:
        if doc.content.startswith(magic):
            stem = re.sub(r"[^A-Za-z0-9 ._-]+", "", doc.name.rsplit(".", 1)[0]).strip()[:80] or "document"
            return content_type, ext, f"{stem}.{ext}"
    raise ApiError("DOCUMENT_TYPE", "Upload a PDF, JPG or PNG file.", status_code=415)


def application_out(r: Any) -> ApplicationOut:
    return ApplicationOut(
        id=r.id, status=r.status, kind=r.kind, org_name=r.org_name, tenant_slug=r.tenant_slug,
        subjects=[SubjectRef(**s) for s in r.subjects], experience=r.experience, document_name=r.document_name,
        payout_bank_name=r.payout_bank_name, payout_branch=r.payout_branch,
        payout_account_name=r.payout_account_name, payout_account_masked=r.payout_account_masked,
        review_note=r.review_note, submitted_at=r.submitted_at, reviewed_at=r.reviewed_at)


@asynccontextmanager
async def _applicant_tx(user_id: UUID) -> AsyncIterator[AsyncSession]:
    async with AppSession() as session, session.begin():
        await session.execute(text("SELECT set_config('app.user_id', :u, true)"), {"u": str(user_id)})
        yield session


async def _latest(session: AsyncSession, user_id: UUID) -> Any:
    return (await session.execute(text(APPLICATION_SELECT + """
        WHERE a.user_id = :u ORDER BY a.created_at DESC LIMIT 1
    """), {"u": user_id})).one_or_none()


async def _applicant(session: AsyncSession, user_id: UUID) -> Any:
    user = (await session.execute(text("""
        SELECT full_name, phone_verified_at IS NOT NULL AS phone_verified FROM users WHERE id = :u
    """), {"u": user_id})).one()
    if not user.phone_verified:
        raise ApiError("PHONE_NOT_VERIFIED", "Verify your mobile number before applying.", status_code=403)
    return user


async def _check_subjects(session: AsyncSession, ids: list[UUID]) -> list[UUID]:
    unique = list(dict.fromkeys(ids))
    found = (await session.execute(text("SELECT count(*) FROM subjects WHERE id = ANY (:ids) AND is_active"),
                                   {"ids": unique})).scalar_one()
    if found != len(unique):
        raise ApiError("SUBJECT_INVALID", "Choose subjects from the list.", status_code=422)
    return unique


async def _tenant_slug(session: AsyncSession, name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:34].strip("-")
    if len(base) < 3:
        base = f"org-{secrets.token_hex(3)}"
    candidate, n = base, 2
    while candidate in RESERVED_SLUGS or (await session.execute(
            text("SELECT 1 FROM resolve_tenant(:s)"), {"s": candidate})).first():
        candidate, n = f"{base}-{n}", n + 1
    return candidate


def _payout_values(fields: ApplicationFields, current: Any = None) -> dict[str, Any]:
    number = fields.payout_account_number
    if number is None and current is None:
        raise ApiError("ACCOUNT_REQUIRED", "Enter the bank account number for your payouts.", status_code=422)
    return {"bank": fields.payout_bank_name, "branch": fields.payout_branch, "aname": fields.payout_account_name,
            "aenc": crypto.encrypt(number) if number else current.payout_account_enc,
            "amask": crypto.mask_account(number) if number else current.payout_account_masked,
            "terms": get_settings().teacher_terms_version}


async def my_application(user_id: UUID) -> ApplicationOut | None:
    async with _applicant_tx(user_id) as session:
        row = await _latest(session, user_id)
    return application_out(row) if row else None


async def apply(user_id: UUID, fields: ApplicationFields, doc: Document, storage: PrivateStorage,
                ip: str | None) -> ApplicationOut:
    content_type, ext, doc_name = check_document(doc)
    payout = _payout_values(fields)
    app_id = uuid4()
    key = f"applications/{app_id}/{secrets.token_hex(8)}.{ext}"
    async with _applicant_tx(user_id) as session:
        user = await _applicant(session, user_id)
        latest = await _latest(session, user_id)
        if latest is not None and latest.status in OPEN_STATUSES:
            raise ApiError("APPLICATION_OPEN", "You already have an application in review.", status_code=409)
        subject_ids = await _check_subjects(session, fields.subject_ids)
        # The file first: if storing it fails, nothing is created.
        await storage.put(key, doc.content, content_type)
        slug = await _tenant_slug(session, fields.org_name)
        # Opens the tenant (pending), makes the applicant its owner and sets app.tenant_id for this transaction.
        tenant_id = (await session.execute(text("SELECT open_pending_tenant(:u, :n, :s, :k, :d)"), {
            "u": user_id, "n": fields.org_name, "s": slug, "k": fields.kind, "d": user.full_name})).scalar_one()
        await profiles.ensure_for_user(session, user_id, user.full_name)
        await session.execute(text("""
            INSERT INTO teacher_applications (id, user_id, tenant_id, kind, org_name, subject_ids, experience,
                document_key, document_name, document_type, payout_bank_name, payout_branch, payout_account_name,
                payout_account_enc, payout_account_masked, terms_version)
            VALUES (:id, :u, :t, :kind, :org, :subjects, :exp, :key, :dname, :dtype, :bank, :branch, :aname,
                    :aenc, :amask, :terms)
        """), {"id": app_id, "u": user_id, "t": tenant_id, "kind": fields.kind, "org": fields.org_name,
               "subjects": subject_ids, "exp": fields.experience, "key": key, "dname": doc_name,
               "dtype": content_type, **payout})
        await write_audit(session, actor_user_id=user_id, action="application.submit",
                          entity_type="teacher_application", entity_id=app_id,
                          details={"org_name": fields.org_name, "kind": fields.kind}, ip=ip)
        return application_out(await _latest(session, user_id))


async def resubmit(user_id: UUID, fields: ApplicationFields, doc: Document | None, storage: PrivateStorage,
                   ip: str | None) -> ApplicationOut:
    """Edit an application still in review (submitted or changes requested); it goes back to `submitted`.
    The organization's type and address stay as opened."""
    async with _applicant_tx(user_id) as session:
        await _applicant(session, user_id)
        latest = await _latest(session, user_id)
        if latest is None or latest.status not in OPEN_STATUSES:
            raise ApiError("APPLICATION_CLOSED", "This application can no longer be changed.", status_code=409)
        if fields.kind != latest.kind:
            raise ApiError("KIND_LOCKED", "Start a new application to change the type of organization.", 409)
        subject_ids = await _check_subjects(session, fields.subject_ids)
        doc_values = {"key": latest.document_key, "dname": latest.document_name, "dtype": latest.document_type}
        if doc is not None:
            content_type, ext, doc_name = check_document(doc)
            key = f"applications/{latest.id}/{secrets.token_hex(8)}.{ext}"
            await storage.put(key, doc.content, content_type)
            doc_values = {"key": key, "dname": doc_name, "dtype": content_type}
        await session.execute(text("""
            UPDATE teacher_applications SET org_name = :org, subject_ids = :subjects, experience = :exp,
                document_key = :key, document_name = :dname, document_type = :dtype, payout_bank_name = :bank,
                payout_branch = :branch, payout_account_name = :aname, payout_account_enc = :aenc,
                payout_account_masked = :amask, terms_version = :terms, status = 'submitted', submitted_at = now()
            WHERE id = :id AND user_id = :u
        """), {"id": latest.id, "u": user_id, "org": fields.org_name, "subjects": subject_ids,
               "exp": fields.experience, **doc_values, **_payout_values(fields, latest)})
        await session.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(latest.tenant_id)})
        await write_audit(session, actor_user_id=user_id, action="application.resubmit",
                          entity_type="teacher_application", entity_id=latest.id,
                          details={"new_document": doc is not None}, ip=ip)
        return application_out(await _latest(session, user_id))
