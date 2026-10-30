"""Phase 5: teacher self-registration and approval. Applying opens a pending organization (draft mode),
the document goes to private storage, the account number is encrypted, and the platform admin decides."""

from collections.abc import AsyncIterator, Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.db import AdminSession
from app.integrations.private_storage import LocalPrivateStorage, get_private_storage
from app.main import app
from tests.conftest import FakeSms, Seed, purge_tenants
from tests.helpers import auth_headers, error_code
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
PDF = b"%PDF-1.4\n% test document\n"
ACCOUNT = "0081 2345 6789"


@pytest.fixture
def storage(tmp_path: Path) -> Iterator[LocalPrivateStorage]:
    store = LocalPrivateStorage(tmp_path)
    app.dependency_overrides[get_private_storage] = lambda: store
    yield store
    app.dependency_overrides.pop(get_private_storage, None)


@pytest.fixture
async def applicant(client: AsyncClient, sms: FakeSms, seed: Seed,
                    phones: Callable[[], str]) -> AsyncIterator[tuple[Headers, str]]:
    phone = phones()
    yield await auth_headers(client, sms, seed.a, phone), phone
    async with AdminSession() as s:
        ids = (await s.execute(text("""
            SELECT a.tenant_id FROM teacher_applications a JOIN users u ON u.id = a.user_id WHERE u.phone = :p
        """), {"p": phone})).scalars().all()
    if ids:
        purge_tenants(list(ids))


async def subject_ids(*slugs: str) -> list[str]:
    async with AdminSession() as s:
        rows = (await s.execute(text("SELECT id FROM subjects WHERE slug = ANY (:s)"), {"s": list(slugs)})).scalars()
        return [str(r) for r in rows]


async def form(**overrides: Any) -> dict[str, Any]:
    return {"kind": "individual", "org_name": "Nimal Physics Classes", "subject_ids": await subject_ids("physics"),
            "experience": "12 years of A/L physics", "payout_bank_name": "Bank of Ceylon", "payout_branch": "Kandy",
            "payout_account_name": "N. Perera", "payout_account_number": ACCOUNT, "accept_terms": "true",
            **overrides}


async def submit(client: AsyncClient, h: Headers, content: bytes = PDF, method: str = "POST",
                 **overrides: Any) -> Any:
    files = {"document": ("nic scan.pdf", content, "application/pdf")} if content else None
    return await client.request(method, "/api/v1/me/teacher-application", headers=h,
                                data=await form(**overrides), files=files)


async def test_apply_opens_a_pending_organization(client: AsyncClient, applicant: tuple[Headers, str],
                                                  storage: LocalPrivateStorage) -> None:
    h, _ = applicant
    assert (await client.get("/api/v1/me/teacher-application", headers=h)).json() is None
    resp = await submit(client, h)
    assert resp.status_code == 201, resp.text
    a = resp.json()
    assert a["status"] == "submitted" and a["tenant_slug"].startswith("nimal-physics-classes")
    assert a["payout_account_masked"] == "****6789" and a["subjects"][0]["name"] == "Physics"
    assert a["document_name"] == "nic scan.pdf"

    async with AdminSession() as s:
        row = (await s.execute(text("""
            SELECT a.payout_account_enc, a.document_key, t.status, t.org_type, m.role
            FROM teacher_applications a JOIN tenants t ON t.id = a.tenant_id
            JOIN tenant_members m ON m.tenant_id = t.id AND m.user_id = a.user_id WHERE a.id = :id
        """), {"id": a["id"]})).one()
    assert row.status == "pending" and row.org_type == "individual" and row.role == "owner"
    assert "6789" not in row.payout_account_enc                # stored encrypted
    assert await storage.get(row.document_key) == PDF          # in private storage, by key only

    # The new owner sees the console as a pending workspace; the public never sees the organization.
    me = (await client.get("/api/v1/auth/me", headers=h)).json()
    assert {"slug": a["tenant_slug"], "name": "Nimal Physics Classes", "role": "owner",
            "status": "pending"} in me["workspaces"]
    assert (await client.get("/api/v1/market/institutes")).status_code == 200
    again = await submit(client, h)
    assert again.status_code == 409 and error_code(again) == "APPLICATION_OPEN"


async def test_draft_mode_allows_building_but_not_publishing(client: AsyncClient, applicant: tuple[Headers, str],
                                                             storage: LocalPrivateStorage) -> None:
    h, _ = applicant
    slug = (await submit(client, h)).json()["tenant_slug"]
    console = f"/api/v1/teach/{slug}"
    c = await client.post(f"{console}/classes", headers=h,
                          json={"title": "A/L Physics 2027", "pricing_model": "monthly", "monthly_fee_cents": 200000})
    assert c.status_code == 201, c.text
    publish = await client.patch(f"{console}/classes/{c.json()['id']}", headers=h, json={"status": "published"})
    assert publish.status_code == 409 and error_code(publish) == "TENANT_NOT_APPROVED"
    # Pending organizations are console-only: no host-based or public resolution.
    assert (await client.get("/api/v1/public/tenant", headers={"host": f"{slug}.localhost"})).status_code == 404


async def test_documents_and_fields_are_checked(client: AsyncClient, applicant: tuple[Headers, str],
                                                storage: LocalPrivateStorage, phones: Callable[[], str],
                                                sms: FakeSms, seed: Seed) -> None:
    h, _ = applicant
    exe = await submit(client, h, content=b"MZ\x90\x00 not a document")
    assert exe.status_code == 415 and error_code(exe) == "DOCUMENT_TYPE"
    big = await submit(client, h, content=b"%PDF-" + b"0" * (10 * 1024 * 1024))
    assert big.status_code == 413
    no_account = await submit(client, h, payout_account_number="")
    assert no_account.status_code == 422 and error_code(no_account) == "ACCOUNT_REQUIRED"
    no_terms = await submit(client, h, accept_terms="false")
    assert no_terms.status_code == 422
    bad_subject = await submit(client, h, subject_ids=["00000000-0000-0000-0000-000000000000"])
    assert bad_subject.status_code == 422 and error_code(bad_subject) == "SUBJECT_INVALID"
    assert (await client.get("/api/v1/me/teacher-application", headers=h)).json() is None   # nothing half-made

    # A phone that was never verified can't apply.
    other_phone = phones()
    other = await auth_headers(client, sms, seed.a, other_phone)
    async with AdminSession() as s, s.begin():
        await s.execute(text("UPDATE users SET phone_verified_at = NULL WHERE phone = :p"), {"p": other_phone})
    unverified = await submit(client, other)
    assert unverified.status_code == 403 and error_code(unverified) == "PHONE_NOT_VERIFIED"


async def test_review_request_changes_resubmit_approve(client: AsyncClient, applicant: tuple[Headers, str],
                                                       storage: LocalPrivateStorage, ph: Headers) -> None:  # noqa: F811
    h, _ = applicant
    a = (await submit(client, h)).json()
    base = f"/api/v1/platform/applications/{a['id']}"

    listed = (await client.get("/api/v1/platform/applications?status=submitted", headers=ph)).json()
    assert any(r["id"] == a["id"] for r in listed)
    detail = (await client.get(base, headers=ph)).json()
    assert detail["payout_account_masked"] == "****6789" and "payout_account_enc" not in detail
    doc = await client.get(f"{base}/document", headers=ph)
    assert doc.status_code == 200 and doc.content == PDF and doc.headers["cache-control"] == "no-store"
    assert (await client.post(f"{base}/reveal-account", headers=ph)).json() == {"account_number": "008123456789"}

    no_note = await client.post(f"{base}/decision", headers=ph, json={"decision": "request_changes"})
    assert no_note.status_code == 422 and error_code(no_note) == "NOTE_REQUIRED"
    changes = await client.post(f"{base}/decision", headers=ph,
                                json={"decision": "request_changes", "note": "The NIC scan is blurry."})
    assert changes.json()["status"] == "changes_requested"
    mine = (await client.get("/api/v1/me/teacher-application", headers=h)).json()
    assert mine["status"] == "changes_requested" and mine["review_note"] == "The NIC scan is blurry."

    # Approving needs a fresh submission.
    early = await client.post(f"{base}/decision", headers=ph, json={"decision": "approve"})
    assert early.status_code == 409
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    resubmitted = await submit(client, h, content=png, method="PUT", payout_account_number="1111 2222 3333")
    assert resubmitted.status_code == 200, resubmitted.text
    assert resubmitted.json()["status"] == "submitted" and resubmitted.json()["document_name"] == "nic scan.png"

    approved = await client.post(f"{base}/decision", headers=ph, json={"decision": "approve"})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    async with AdminSession() as s:
        t = (await s.execute(text("SELECT status, payout_bank_name, payout_account_masked FROM tenants WHERE id = :t"),
                             {"t": detail["tenant_id"]})).one()
        actions = set((await s.execute(text("SELECT action FROM audit_logs WHERE entity_id = :a"),
                                       {"a": a["id"]})).scalars())
    assert tuple(t) == ("active", "Bank of Ceylon", "****3333")
    assert {"application.submit", "application.resubmit", "platform.application.document",
            "platform.application.reveal_account", "platform.application.request_changes",
            "platform.application.approve"} <= actions
    closed = await submit(client, h, method="PUT", content=b"")
    assert closed.status_code == 409 and error_code(closed) == "APPLICATION_CLOSED"

    # Approved: publishing now works.
    console = f"/api/v1/teach/{a['tenant_slug']}"
    c = (await client.post(f"{console}/classes", headers=h, json={
        "title": "Physics", "pricing_model": "one_time", "one_time_price_cents": 100000})).json()
    assert (await client.patch(f"{console}/classes/{c['id']}", headers=h,
                               json={"status": "published"})).status_code == 200


async def test_reject_closes_the_organization(client: AsyncClient, applicant: tuple[Headers, str],
                                              storage: LocalPrivateStorage, ph: Headers) -> None:  # noqa: F811
    h, _ = applicant
    a = (await submit(client, h)).json()
    resp = await client.post(f"/api/v1/platform/applications/{a['id']}/decision", headers=ph,
                             json={"decision": "reject", "note": "We could not verify the documents."})
    assert resp.json()["status"] == "rejected"
    me = (await client.get("/api/v1/auth/me", headers=h)).json()
    assert all(w["slug"] != a["tenant_slug"] for w in me["workspaces"])
    assert (await client.get(f"/api/v1/teach/{a['tenant_slug']}/classes", headers=h)).status_code == 404
    # A rejected applicant may apply again (a new organization).
    again = await submit(client, h, org_name="Nimal Physics")
    assert again.status_code == 201 and again.json()["tenant_slug"].startswith("nimal-physics")


async def test_students_and_staff_cannot_review(client: AsyncClient, applicant: tuple[Headers, str],
                                                storage: LocalPrivateStorage) -> None:
    h, _ = applicant
    a = (await submit(client, h)).json()
    assert (await client.get("/api/v1/platform/applications", headers=h)).status_code == 401
    assert (await client.post(f"/api/v1/platform/applications/{a['id']}/decision", headers=h,
                              json={"decision": "approve"})).status_code == 401
