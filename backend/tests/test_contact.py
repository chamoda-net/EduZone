"""The contact form and the support inbox: storing, the two emails, limits, the honeypot, staff replies."""

from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass, field
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import AdminSession, AppSession
from app.integrations.email import get_email_sender
from app.main import app
from tests.conftest import FakeSms, Seed
from tests.helpers import auth_headers, error_code
from tests.test_platform import padmin, ph  # noqa: F401  (fixtures)

Headers = dict[str, str]
URL = "/api/v1/market/contact"
P = "/api/v1/platform/contact"


@dataclass
class Mail:
    sent: list[dict[str, str | None]] = field(default_factory=list)

    async def send(self, to: str, subject: str, body: str, *, reply_to: str | None = None) -> None:
        self.sent.append({"to": to, "subject": subject, "body": body, "reply_to": reply_to})


@pytest.fixture
def mail() -> Iterator[Mail]:
    fake = Mail()
    app.dependency_overrides[get_email_sender] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_email_sender, None)


@pytest.fixture
async def sender() -> AsyncIterator[str]:
    email = f"contact-{uuid4().hex[:10]}@example.com"
    yield email
    async with AdminSession() as s, s.begin():
        await s.execute(text("DELETE FROM contact_messages WHERE lower(email) = :e"), {"e": email})


def form(email: str, **extra: object) -> dict[str, object]:
    return {"name": "Nimal Perera", "email": email, "phone": "077 123 4567", "topic": "payments",
            "subject": "Paid but no access", "message": "I paid for November but the lessons are still locked.",
            **extra}


async def test_a_message_is_stored_and_both_emails_go_out(client: AsyncClient, mail: Mail, sender: str) -> None:
    resp = await client.post(URL, json=form(sender))
    assert resp.status_code == 202, resp.text
    ref = resp.json()["reference"]
    assert ref.startswith("EZ-") and len(ref) == 9

    async with AdminSession() as s:
        row = (await s.execute(text("SELECT * FROM contact_messages WHERE reference = :r"), {"r": ref})).one()
    assert row.status == "new" and row.phone == "+94771234567" and row.user_id is None

    inbox, receipt = mail.sent
    assert inbox["to"] == get_settings().support_inbox_email and inbox["reply_to"] == sender
    assert ref in str(inbox["subject"]) and "Payments and refunds" in str(inbox["subject"])
    assert receipt["to"] == sender and ref in str(receipt["subject"]) and "Hi Nimal" in str(receipt["body"])
    assert "> I paid for November" in str(receipt["body"])


async def test_the_app_role_cannot_read_messages(client: AsyncClient, mail: Mail, sender: str) -> None:
    assert (await client.post(URL, json=form(sender))).status_code == 202
    async with AppSession() as s:
        with pytest.raises(Exception, match="permission denied"):
            await s.execute(text("SELECT * FROM contact_messages"))


async def test_validation_and_honeypot(client: AsyncClient, mail: Mail, sender: str) -> None:
    assert (await client.post(URL, json=form(sender, message="short"))).status_code == 422
    assert (await client.post(URL, json=form(sender, topic="refund"))).status_code == 422
    assert (await client.post(URL, json=form(sender, phone="12"))).status_code == 422
    assert (await client.post(URL, json=form("not-an-email"))).status_code == 422
    # The hidden field: it looks sent, but nothing is stored or emailed.
    bot = await client.post(URL, json=form(sender, website="http://spam.example"))
    assert bot.status_code == 202 and bot.json()["reference"].startswith("EZ-")
    assert mail.sent == []
    async with AdminSession() as s:
        assert (await s.execute(text("SELECT count(*) FROM contact_messages WHERE email = :e"),
                                {"e": sender})).scalar_one() == 0


async def test_three_an_hour_per_address(client: AsyncClient, mail: Mail, sender: str) -> None:
    for _ in range(3):
        assert (await client.post(URL, json=form(sender))).status_code == 202
    again = await client.post(URL, json=form(sender.upper()))
    assert again.status_code == 429 and error_code(again) == "CONTACT_RATE_LIMITED"


async def test_signed_in_sender_is_linked(client: AsyncClient, mail: Mail, sender: str, seed: Seed,
                                          sms: FakeSms) -> None:
    h = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    ref = (await client.post(URL, json=form(sender), headers=h)).json()["reference"]
    async with AdminSession() as s:
        assert (await s.execute(text("SELECT user_id FROM contact_messages WHERE reference = :r"),
                                {"r": ref})).scalar_one() is not None


async def test_staff_reply_from_the_inbox(client: AsyncClient, mail: Mail, sender: str, ph: Headers) -> None:
    ref = (await client.post(URL, json=form(sender))).json()["reference"]
    page = (await client.get(P, headers=ph, params={"q": ref})).json()
    assert [m["reference"] for m in page["items"]] == [ref]
    assert page["items"][0]["status"] == "new" and page["counts"]["new"] >= 1
    msg_id = page["items"][0]["id"]

    detail = (await client.get(f"{P}/{msg_id}", headers=ph)).json()
    assert detail["status"] == "open" and detail["phone"] == "+94771234567" and detail["reply_list"] == []
    assert (await client.get(P, headers=ph, params={"status": "active", "q": ref})).json()["items"]

    mail.sent.clear()
    replied = await client.post(f"{P}/{msg_id}/reply", headers=ph,
                                json={"body": "Sorry about that, November is open for you now."})
    assert replied.status_code == 200, replied.text
    out = replied.json()
    assert out["status"] == "replied" and out["reply_list"][0]["author_name"] == "EduZone Staff"
    (email,) = mail.sent
    assert email["to"] == sender and ref in str(email["subject"]) and str(email["subject"]).startswith("Re: ")
    assert "November is open" in str(email["body"]) and "> I paid for November" in str(email["body"])

    closed = await client.patch(f"{P}/{msg_id}", headers=ph, json={"status": "closed", "staff_note": "Fixed grant"})
    assert closed.json()["status"] == "closed" and closed.json()["staff_note"] == "Fixed grant"
    assert (await client.patch(f"{P}/{msg_id}", headers=ph, json={"status": None})).status_code == 422

    audit = (await client.get("/api/v1/platform/audit", headers=ph, params={"entity_id": msg_id})).json()["items"]
    assert [a["action"] for a in audit] == ["platform.contact.update", "platform.contact.reply"]


async def test_inbox_needs_an_admin(client: AsyncClient, seed: Seed, sms: FakeSms) -> None:
    owner = await auth_headers(client, sms, seed.a, seed.a.teacher_phone)
    assert (await client.get(P, headers=owner)).status_code == 401
    assert (await client.get(P)).status_code == 401
