"""Accounts, sign-in, devices, phone and email checks, recovery (CLAUDE.md sections 10-11)."""

import re
from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass, field
from uuid import uuid4

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import text

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from app.integrations.email import get_email_sender
from app.main import app
from app.modules.auth.google import GoogleIdentity, get_google_verifier
from app.modules.auth.phone import normalize_phone
from tests.conftest import FakeSms, Seed, SeededTenant
from tests.helpers import (
    PASSWORD,
    Phones,
    ensure_account,
    error_code,
    login,
    me,
    password_login,
    refresh,
    skip_cooldown,
)

# --- fixtures ----------------------------------------------------------------------------


@dataclass
class FakeEmail:
    sent: list[tuple[str, str, str]] = field(default_factory=list)

    async def send(self, to: str, subject: str, body: str) -> None:
        self.sent.append((to, subject, body))

    def last_link(self, to: str) -> str:
        body = next(b for t, _, b in reversed(self.sent) if t == to)
        return re.search(r"https?://\S+", body).group(0)  # type: ignore[union-attr]


@pytest.fixture
def mail() -> Iterator[FakeEmail]:
    fake = FakeEmail()
    app.dependency_overrides[get_email_sender] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_email_sender, None)


@pytest.fixture
async def emails() -> AsyncIterator[Callable[[], str]]:
    """Fresh email addresses; accounts made with them are removed afterwards."""
    made: list[str] = []

    def make() -> str:
        made.append(f"t-{uuid4().hex[:10]}@example.com")
        return made[-1]

    yield make
    async with AdminSession() as s, s.begin():
        await s.execute(text("DELETE FROM login_attempts WHERE email = ANY(:e)"), {"e": made})
        await s.execute(text("DELETE FROM otp_codes WHERE destination IN "
                             "(SELECT phone FROM users WHERE email = ANY(:e))"), {"e": made})
        await s.execute(text("DELETE FROM users WHERE email = ANY(:e)"), {"e": made})


class FakeGoogle:
    def __init__(self) -> None:
        self.identity = GoogleIdentity("google-sub", None, False, None)

    def verify(self, id_token: str) -> GoogleIdentity:
        return self.identity


@pytest.fixture
def google() -> Iterator[FakeGoogle]:
    fake = FakeGoogle()
    app.dependency_overrides[get_google_verifier] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_google_verifier, None)


def host(t: SeededTenant) -> dict[str, str]:
    return {"host": t.host}


def bearer(t: SeededTenant, access: str) -> dict[str, str]:
    return {"host": t.host, "authorization": f"Bearer {access}"}


async def register(client: AsyncClient, t: SeededTenant, email: str, password: str = PASSWORD,
                   device: str = "device-0001", name: str = "  Nimali   Silva ") -> Response:
    return await client.post("/api/v1/auth/register", headers=host(t), json={
        "email": email, "password": password, "full_name": name, "device_id": device})


# --- phone numbers -----------------------------------------------------------------------

@pytest.mark.parametrize(("raw", "expected"), [
    ("0771234567", "+94771234567"),
    ("077 123 4567", "+94771234567"),
    ("94771234567", "+94771234567"),
    ("+94771234567", "+94771234567"),
    ("+447911123456", "+447911123456"),
])
def test_normalize_phone(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize("raw", ["", "12345", "077123456", "+0771234567", "phone"])
def test_normalize_phone_rejects(raw: str) -> None:
    with pytest.raises(ValueError):
        normalize_phone(raw)


# --- register ----------------------------------------------------------------------------

async def test_register_signs_in_and_emails_a_link(client: AsyncClient, seed: Seed, mail: FakeEmail,
                                                   emails: Callable[[], str]) -> None:
    email = emails()
    resp = await register(client, seed.a, email.upper())
    assert resp.status_code == 201, resp.text
    profile = (await me(client, seed.a, resp.json()["access_token"])).json()
    assert profile["email"] == email and profile["full_name"] == "Nimali Silva"
    assert profile["email_verified"] is False and profile["phone_verified"] is False
    # Signing up doesn't make anyone a member of the tenant.
    assert profile["member_id"] is None and profile["role"] is None

    link = mail.last_link(email)
    assert link.startswith(f"https://{seed.a.host}/verify-email?token=") or link.startswith(f"http://{seed.a.host}/")
    token = link.split("token=")[1]
    assert (await client.post("/api/v1/auth/email/verify", json={"token": token})).status_code == 204
    assert (await me(client, seed.a, resp.json()["access_token"])).json()["email_verified"] is True
    again = await client.post("/api/v1/auth/email/verify", json={"token": token})
    assert again.status_code == 400 and error_code(again) == "LINK_INVALID"


async def test_register_rejects_taken_email_and_short_password(client: AsyncClient, seed: Seed, mail: FakeEmail,
                                                               emails: Callable[[], str]) -> None:
    email = emails()
    assert (await register(client, seed.a, email)).status_code == 201
    dup = await register(client, seed.a, email)
    assert dup.status_code == 409 and error_code(dup) == "EMAIL_TAKEN"
    short = await register(client, seed.a, emails(), password="short")
    assert short.status_code == 422
    async with AdminSession() as s:
        stored = (await s.execute(text("SELECT password_hash FROM users WHERE email = :e"), {"e": email})).scalar_one()
    assert stored.startswith("$argon2id$") and PASSWORD not in stored


async def test_register_needs_a_known_site(client: AsyncClient, mail: FakeEmail, emails: Callable[[], str]) -> None:
    # Links are built from the host, so registration only works on a site we serve.
    resp = await client.post("/api/v1/auth/register", headers={"host": "evil.example.org"}, json={
        "email": emails(), "password": PASSWORD, "full_name": "X", "device_id": "device-0001"})
    assert resp.status_code == 404 and mail.sent == []


# --- password sign-in --------------------------------------------------------------------

async def test_wrong_password_and_unknown_email_look_the_same(client: AsyncClient, seed: Seed, sms: FakeSms,
                                                              phones: Phones) -> None:
    email = await ensure_account(phones())
    wrong = await password_login(client, seed.a, email, "Not-the-password")
    unknown = await password_login(client, seed.a, f"nobody-{uuid4().hex[:6]}@example.com")
    assert wrong.status_code == unknown.status_code == 400
    assert error_code(wrong) == error_code(unknown) == "LOGIN_INVALID"


async def test_failed_sign_ins_are_throttled(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    email = await ensure_account(phones())
    for _ in range(8):
        assert (await password_login(client, seed.a, email, "Wrong-password")).status_code == 400
    blocked = await password_login(client, seed.a, email)  # even the right password now waits
    assert blocked.status_code == 429 and error_code(blocked) == "LOGIN_RATE_LIMITED"
    async with AdminSession() as s, s.begin():
        await s.execute(text("DELETE FROM login_attempts WHERE email = :e"), {"e": email})


async def test_known_device_signs_in_without_sms(client: AsyncClient, seed: Seed, sms: FakeSms,
                                                 phones: Phones) -> None:
    phone = phones()
    await login(client, sms, seed.a, phone, device="device-home")      # SMS check once
    sent = len(sms.sent)
    resp = await password_login(client, seed.a, await ensure_account(phone), device="device-home")
    assert resp.json()["status"] == "signed_in" and len(sms.sent) == sent


async def test_new_device_needs_the_sms_code(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    email = await ensure_account(phone)
    resp = await password_login(client, seed.a, email, device="device-new")
    check = resp.json()
    assert check["status"] == "device_check" and check["tokens"] is None
    assert check["device_check"]["phone_hint"] == f"•••• {phone[-4:]}"
    challenge = check["device_check"]["challenge"]

    wrong = await client.post("/api/v1/auth/device/verify", json={
        "challenge": challenge, "code": "000000" if sms.last_code(phone) != "000000" else "111111",
        "device_id": "device-new"})
    assert wrong.status_code == 400 and error_code(wrong) == "OTP_INVALID"
    # The challenge is bound to the device that started it.
    other = await client.post("/api/v1/auth/device/verify", json={
        "challenge": challenge, "code": sms.last_code(phone), "device_id": "device-else"})
    assert other.status_code == 401 and error_code(other) == "CHALLENGE_EXPIRED"
    ok = await client.post("/api/v1/auth/device/verify", json={
        "challenge": challenge, "code": sms.last_code(phone), "device_id": "device-new"})
    assert ok.status_code == 200 and ok.json()["access_token"]


async def test_one_device_per_account(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    first = await login(client, sms, seed.a, phone, device="device-one")
    await skip_cooldown(phone)
    await login(client, sms, seed.b, phone, device="device-two")  # another tenant, same account
    ended = await me(client, seed.a, first["access_token"])
    assert ended.status_code == 401 and error_code(ended) == "SIGNED_IN_ELSEWHERE"
    gone = await refresh(client, seed.a, first["refresh_token"])
    assert gone.status_code == 401 and error_code(gone) == "SIGNED_IN_ELSEWHERE"


async def test_staff_may_use_several_devices(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    first = await login(client, sms, seed.a, seed.a.teacher_phone, device="device-laptop")
    await skip_cooldown(seed.a.teacher_phone)
    await login(client, sms, seed.a, seed.a.teacher_phone, device="device-phone")
    assert (await me(client, seed.a, first["access_token"])).status_code == 200


async def test_account_without_a_phone_signs_in_anywhere(client: AsyncClient, seed: Seed, sms: FakeSms,
                                                        mail: FakeEmail, emails: Callable[[], str]) -> None:
    email = emails()
    await register(client, seed.a, email, device="device-one")
    resp = await password_login(client, seed.a, email, device="device-two")
    assert resp.json()["status"] == "signed_in" and sms.sent == []


# --- one account across tenants ----------------------------------------------------------

async def test_account_works_on_every_tenant_with_its_role_there(client: AsyncClient, seed: Seed,
                                                                 sms: FakeSms) -> None:
    tokens = await login(client, sms, seed.a, seed.a.teacher_phone)
    on_a = (await me(client, seed.a, tokens["access_token"])).json()
    on_b = (await me(client, seed.b, tokens["access_token"])).json()
    assert on_a["role"] == "teacher" and on_a["member_id"] == str(seed.a.member_id)
    assert on_b["role"] is None and on_b["member_id"] is None
    # Staff routes need staff membership in *this* tenant.
    staff_b = await client.get("/api/v1/org/classes", headers=bearer(seed.b, tokens["access_token"]))
    assert staff_b.status_code == 403


async def test_joining_makes_a_member(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    tokens = await login(client, sms, seed.a, phones())
    h = bearer(seed.a, tokens["access_token"])
    async with tenant_transaction(seed.a.id) as s:
        slug = (await s.execute(text("SELECT slug FROM classes WHERE id = :c"), {"c": seed.a.class_id})).scalar_one()
        await s.execute(text("UPDATE classes SET status = 'published' WHERE id = :c"), {"c": seed.a.class_id})
    assert (await client.get("/api/v1/student/classes", headers=h)).json() == []
    assert (await client.post(f"/api/v1/student/classes/{slug}/enroll", headers=h)).status_code == 200
    profile = (await me(client, seed.a, tokens["access_token"])).json()
    assert profile["role"] == "student" and profile["member_id"] is not None


async def test_suspended_member_is_refused_on_that_tenant(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    tokens = await login(client, sms, seed.a, seed.a.teacher_phone)
    async with tenant_transaction(seed.a.id) as s:
        await s.execute(text("UPDATE tenant_members SET status = 'suspended' WHERE id = :m"), {"m": seed.a.member_id})
    resp = await me(client, seed.a, tokens["access_token"])
    assert resp.status_code == 403 and error_code(resp) == "ACCOUNT_SUSPENDED"
    assert (await me(client, seed.b, tokens["access_token"])).status_code == 200


# --- tokens and sessions -----------------------------------------------------------------

@pytest.mark.parametrize("header", ["", "Bearer", "Bearer not-a-jwt", "Basic abc"])
async def test_bad_authorization_is_401(client: AsyncClient, seed: Seed, header: str) -> None:
    resp = await client.get("/api/v1/auth/me", headers={"host": seed.a.host, "authorization": header})
    assert resp.status_code == 401


async def test_refresh_rotates_token(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    tokens = await login(client, sms, seed.a, phones())
    rotated = await refresh(client, seed.a, tokens["refresh_token"])
    assert rotated.status_code == 200
    assert (await refresh(client, seed.a, tokens["refresh_token"])).status_code == 401
    assert (await refresh(client, seed.a, rotated.json()["refresh_token"])).status_code == 200


async def test_logout_ends_session(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    tokens = await login(client, sms, seed.a, phones())
    h = bearer(seed.a, tokens["access_token"])
    assert (await client.post("/api/v1/auth/logout", headers=h)).status_code == 204
    assert (await me(client, seed.a, tokens["access_token"])).status_code == 401
    assert (await refresh(client, seed.a, tokens["refresh_token"])).status_code == 401


async def test_secrets_are_stored_hashed(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    phone = phones()
    tokens = await login(client, sms, seed.a, phone)
    async with AdminSession() as s:
        stored = (await s.execute(text("SELECT refresh_token_hash FROM user_sessions s JOIN users u "
                                       "ON u.id = s.user_id WHERE u.phone = :p"), {"p": phone})).scalar_one()
        code_hashes = (await s.execute(text("SELECT code_hash FROM otp_codes WHERE destination = :p"),
                                       {"p": phone})).scalars().all()
    assert stored != tokens["refresh_token"] and len(stored) == 64
    assert all(h != sms.last_code(phone) and len(h) == 64 for h in code_hashes)


# --- phone verification ------------------------------------------------------------------

async def test_verify_phone(client: AsyncClient, seed: Seed, sms: FakeSms, mail: FakeEmail,
                            emails: Callable[[], str], phones: Phones) -> None:
    tokens = (await register(client, seed.a, emails(), device="device-one")).json()
    h = bearer(seed.a, tokens["access_token"])
    phone = phones()
    sent = await client.post("/api/v1/auth/phone/request", headers=h, json={"phone": "0" + phone[3:]})
    assert sent.status_code == 202 and sent.json()["resend_after"] > 0
    wait = await client.post("/api/v1/auth/phone/request", headers=h, json={"phone": phone})
    assert wait.status_code == 429 and error_code(wait) == "OTP_RATE_LIMITED"
    ok = await client.post("/api/v1/auth/phone/verify", headers=h, json={
        "phone": phone, "code": sms.last_code(phone), "device_id": "device-one"})
    assert ok.status_code == 204
    profile = (await me(client, seed.a, tokens["access_token"])).json()
    assert profile["phone"] == phone and profile["phone_verified"] is True


async def test_phone_linked_to_another_account(client: AsyncClient, seed: Seed, sms: FakeSms, mail: FakeEmail,
                                               emails: Callable[[], str], phones: Phones) -> None:
    taken = phones()
    await ensure_account(taken)
    tokens = (await register(client, seed.a, emails())).json()
    resp = await client.post("/api/v1/auth/phone/request", headers=bearer(seed.a, tokens["access_token"]),
                             json={"phone": taken})
    assert resp.status_code == 409 and error_code(resp) == "PHONE_IN_USE"
    assert not [p for p, _ in sms.sent if p == taken]


async def test_paying_needs_a_verified_phone(client: AsyncClient, seed: Seed, mail: FakeEmail,
                                             emails: Callable[[], str]) -> None:
    tokens = (await register(client, seed.a, emails())).json()
    resp = await client.post("/api/v1/student/checkout", headers=bearer(seed.a, tokens["access_token"]),
                             json={"class_id": str(seed.a.class_id)})
    assert resp.status_code == 403 and error_code(resp) == "PHONE_NOT_VERIFIED"


# --- profile -----------------------------------------------------------------------------

async def test_update_profile(client: AsyncClient, seed: Seed, sms: FakeSms, phones: Phones) -> None:
    tokens = await login(client, sms, seed.a, phones())
    h = bearer(seed.a, tokens["access_token"])
    resp = await client.patch("/api/v1/auth/me", headers=h, json={
        "full_name": " Kamal  Perera ", "exam": "al", "exam_year": 2027, "school": "Royal College"})
    assert resp.status_code == 200
    body = resp.json()
    assert (body["full_name"], body["exam"], body["exam_year"], body["school"]) == \
        ("Kamal Perera", "al", 2027, "Royal College")
    assert (await client.patch("/api/v1/auth/me", headers=h, json={"full_name": None})).status_code == 422
    assert (await client.patch("/api/v1/auth/me", headers=h, json={"is_platform_admin": True})).status_code == 422


# --- recovery ----------------------------------------------------------------------------

async def test_recovery_with_email_link_and_sms(client: AsyncClient, seed: Seed, sms: FakeSms, mail: FakeEmail,
                                                phones: Phones) -> None:
    phone = phones()
    email = await ensure_account(phone)
    old = await login(client, sms, seed.a, phone, device="device-old")

    assert (await client.post("/api/v1/auth/recovery/request", headers=host(seed.a),
                              json={"email": email})).status_code == 202
    token = mail.last_link(email).rsplit("/", 1)[1]
    await skip_cooldown(phone)
    started = await client.post("/api/v1/auth/recovery/start", json={"token": token})
    assert started.json() == {"needs_code": True, "phone_hint": f"•••• {phone[-4:]}", "resend_after": 60}

    no_code = await client.post("/api/v1/auth/recovery/complete", json={
        "token": token, "password": "A-new-password-1", "device_id": "device-new"})
    assert no_code.status_code == 400 and error_code(no_code) == "OTP_REQUIRED"
    done = await client.post("/api/v1/auth/recovery/complete", json={
        "token": token, "code": sms.last_code(phone), "password": "A-new-password-1", "device_id": "device-new"})
    assert done.status_code == 200 and done.json()["access_token"]

    assert (await me(client, seed.a, old["access_token"])).status_code == 401      # everywhere signed out
    assert error_code(await password_login(client, seed.a, email)) == "LOGIN_INVALID"
    fresh = await password_login(client, seed.a, email, "A-new-password-1", device="device-new")
    assert fresh.json()["status"] == "signed_in"                                    # this device is now known
    reused = await client.post("/api/v1/auth/recovery/start", json={"token": token})
    assert reused.status_code == 400 and error_code(reused) == "LINK_INVALID"


async def test_recovery_says_nothing_about_unknown_emails(client: AsyncClient, seed: Seed,
                                                          mail: FakeEmail) -> None:
    resp = await client.post("/api/v1/auth/recovery/request", headers=host(seed.a),
                             json={"email": f"nobody-{uuid4().hex[:6]}@example.com"})
    assert resp.status_code == 202 and mail.sent == []


async def test_owner_without_password_sets_one_by_recovery(client: AsyncClient, seed: Seed, mail: FakeEmail,
                                                           emails: Callable[[], str]) -> None:
    email = emails()
    async with AdminSession() as s, s.begin():
        await s.execute(text("INSERT INTO users (email, full_name) VALUES (:e, 'New Owner')"), {"e": email})
    await client.post("/api/v1/auth/recovery/request", headers=host(seed.a), json={"email": email})
    token = mail.last_link(email).rsplit("/", 1)[1]
    assert (await client.post("/api/v1/auth/recovery/start", json={"token": token})).json()["needs_code"] is False
    done = await client.post("/api/v1/auth/recovery/complete", json={
        "token": token, "password": "Owner-password-1", "device_id": "device-0001"})
    assert done.status_code == 200
    profile = (await me(client, seed.a, done.json()["access_token"])).json()
    assert profile["email_verified"] is True and profile["has_password"] is True


# --- Google ------------------------------------------------------------------------------

async def test_google_creates_then_reuses_the_account(client: AsyncClient, seed: Seed, google: FakeGoogle,
                                                      emails: Callable[[], str]) -> None:
    email = emails()
    google.identity = GoogleIdentity(f"sub-{uuid4().hex}", email, True, "Ayesha Fernando")
    first = await client.post("/api/v1/auth/google", json={"id_token": "x" * 40, "device_id": "device-0001"})
    assert first.status_code == 200 and first.json()["status"] == "signed_in"
    profile = (await me(client, seed.a, first.json()["tokens"]["access_token"])).json()
    assert profile["full_name"] == "Ayesha Fernando" and profile["email_verified"] and not profile["has_password"]
    again = await client.post("/api/v1/auth/google", json={"id_token": "x" * 40, "device_id": "device-0001"})
    assert (await me(client, seed.a, again.json()["tokens"]["access_token"])).json()["user_id"] == profile["user_id"]


async def test_google_takes_back_an_unverified_email(client: AsyncClient, seed: Seed, google: FakeGoogle,
                                                     mail: FakeEmail, emails: Callable[[], str]) -> None:
    # Someone registered the address without proving it; the real owner arrives with Google.
    email = emails()
    squatter = (await register(client, seed.a, email, device="device-squat")).json()
    google.identity = GoogleIdentity(f"sub-{uuid4().hex}", email, True, "Real Owner")
    resp = await client.post("/api/v1/auth/google", json={"id_token": "x" * 40, "device_id": "device-real"})
    assert resp.status_code == 200
    assert (await me(client, seed.a, squatter["access_token"])).status_code == 401
    assert error_code(await password_login(client, seed.a, email, device="device-squat")) == "LOGIN_INVALID"


async def test_google_needs_a_verified_email(client: AsyncClient, google: FakeGoogle) -> None:
    google.identity = GoogleIdentity(f"sub-{uuid4().hex}", "someone@example.com", False, None)
    resp = await client.post("/api/v1/auth/google", json={"id_token": "x" * 40, "device_id": "device-0001"})
    assert resp.status_code == 400 and error_code(resp) == "GOOGLE_EMAIL_UNVERIFIED"


async def test_google_off_until_configured(client: AsyncClient) -> None:
    resp = await client.post("/api/v1/auth/google", json={"id_token": "x" * 40, "device_id": "device-0001"})
    assert resp.status_code == 503 and error_code(resp) == "GOOGLE_NOT_CONFIGURED"
