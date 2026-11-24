"""The contact form and the support inbox.

Sending: the message is stored first (submit_contact_message(), SECURITY DEFINER, which also applies the limits),
then two emails go out: a copy to the support inbox that replies to the sender, and a receipt to the sender with
the reference. A failed email never loses the message: it is in the inbox either way.

Replying (platform admin): the reply is stored, emailed to the sender with the reference in the subject, and the
message becomes `replied` (or `closed`). Every change is audited.
"""

import logging
import secrets
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.pagination import decode_cursor, encode_cursor
from app.integrations.email import EmailSender
from app.modules.contact.schemas import (
    ContactCounts,
    ContactDetail,
    ContactIn,
    ContactPage,
    ContactReply,
    ContactRow,
    ContactSent,
    ContactStatus,
    ContactUpdate,
    ReplyIn,
)
from app.modules.platform.auth import PlatformActor
from app.modules.platform.service import _audit

log = logging.getLogger("eduzone.contact")

TOPIC_LABELS: dict[str, str] = {
    "classes": "A class or teacher",
    "payments": "Payments and refunds",
    "account": "My account",
    "teaching": "Teaching on EduZone",
    "institutes": "Institutes",
    "courses": "Courses",
    "partnership": "Partnerships and press",
    "other": "Something else",
}

RATE_LIMITED = ApiError("CONTACT_RATE_LIMITED",
                        "You've sent a few messages already. Please wait an hour, or reply to our email.", 429)


# --- sending ---------------------------------------------------------------------------------------

async def submit(body: ContactIn, *, user_id: UUID | None, ip: str | None, ua: str | None,
                 emails: EmailSender) -> ContactSent:
    if body.website:
        # A bot filled the hidden field: look successful, store and send nothing.
        log.info("contact honeypot hit from %s", ip)
        return ContactSent(reference="EZ-" + "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6)))
    async with AppSession() as session, session.begin():
        reference = (await session.execute(text("""
            SELECT submit_contact_message(:u, :name, :email, :phone, :topic, :subject, :message, CAST(:ip AS inet), :ua)
        """), {"u": user_id, "name": body.name, "email": str(body.email), "phone": body.phone, "topic": body.topic,
               "subject": body.subject, "message": body.message, "ip": ip, "ua": ua})).scalar_one()
    if reference is None:
        raise RATE_LIMITED

    s = get_settings()
    topic = TOPIC_LABELS[body.topic]
    first = body.name.split()[0]
    await _send(emails, s.support_inbox_email, f"[{reference}] {topic}: {body.subject}", "\n".join([
        f"New message from the contact form ({reference})",
        "",
        f"From:    {body.name} <{body.email}>",
        f"Phone:   {body.phone or '-'}",
        f"Topic:   {topic}",
        f"Account: {'signed in' if user_id else 'not signed in'}",
        "",
        body.message,
        "",
        "Reply from the admin app's Inbox so the student gets the answer and it is kept with the message.",
    ]), reply_to=str(body.email))
    await _send(emails, str(body.email), f"We've got your message [{reference}]", "\n".join([
        f"Hi {first},",
        "",
        "Thanks for writing to EduZone. A person on our team will read your message and reply to this email "
        "address, usually within one working day (Monday to Friday, 9:00 to 17:00 Sri Lanka time).",
        "",
        f"Your reference: {reference}",
        "",
        "For a question about a class (times, tutes, Zoom), the teacher can often answer faster: their contact "
        "details are on the class page.",
        "",
        "What you sent:",
        f"Subject: {body.subject}",
        "",
        _quote(body.message),
        "",
        "The EduZone team",
    ]))
    return ContactSent(reference=reference)


async def _send(emails: EmailSender, to: str, subject: str, body: str, *, reply_to: str | None = None) -> None:
    try:
        await emails.send(to, subject, body, reply_to=reply_to)
    except Exception:  # the message is stored; staff see it in the inbox even if an email fails
        log.exception("contact email to %s failed", to)


def _quote(message: str) -> str:
    return "\n".join(f"> {line}" for line in message.splitlines())


# --- the inbox -------------------------------------------------------------------------------------

_ROW = """
    SELECT m.id, m.reference, m.name, m.email, m.topic, m.subject, left(m.message, 160) AS preview, m.status,
           m.user_id IS NOT NULL AS signed_in, m.created_at, m.last_reply_at,
           (SELECT count(*) FROM contact_replies r WHERE r.message_id = m.id) AS replies
    FROM contact_messages m
"""


def _pick(model: Any, r: Any) -> Any:
    return model.model_validate({k: getattr(r, k) for k in model.model_fields})


async def list_messages(session: AsyncSession, *, status: str | None, q: str | None, cursor: str | None,
                        limit: int) -> ContactPage:
    after = decode_cursor(cursor) if cursor else None
    like = f"%{q.strip()}%" if q and q.strip() else None
    rows = (await session.execute(text(f"""
        {_ROW}
        WHERE (CAST(:st AS text) IS NULL OR (:st = 'active' AND m.status IN ('new','open')) OR m.status = :st)
          AND (CAST(:like AS text) IS NULL OR m.reference ILIKE :like OR m.email ILIKE :like OR m.name ILIKE :like
               OR m.subject ILIKE :like)
          AND (CAST(:after_ts AS timestamptz) IS NULL OR (m.created_at, m.id) < (:after_ts, :after_id))
        ORDER BY m.created_at DESC, m.id DESC
        LIMIT :limit
    """), {"st": status, "like": like, "after_ts": after[0] if after else None,
           "after_id": after[1] if after else None, "limit": limit + 1})).all()
    counts = dict((await session.execute(text(
        "SELECT status, count(*) FROM contact_messages GROUP BY status"))).all())
    page = rows[:limit]
    return ContactPage(
        items=[_pick(ContactRow, r) for r in page],
        next_cursor=encode_cursor(page[-1].created_at, page[-1].id) if len(rows) > limit else None,
        counts=ContactCounts(**{k: counts.get(k, 0) for k in ContactCounts.model_fields}),
    )


async def get_message(session: AsyncSession, message_id: UUID, *, mark_open: bool = True) -> ContactDetail:
    if mark_open:  # opening a new message moves it to `open` (seen, not answered yet)
        await session.execute(text("""
            UPDATE contact_messages SET status = 'open', updated_at = now() WHERE id = :id AND status = 'new'
        """), {"id": message_id})
    r = (await session.execute(text("""
        SELECT m.*, host(m.ip) AS ip_text, u.full_name AS user_name,
               (SELECT count(*) FROM contact_messages o WHERE lower(o.email) = lower(m.email) AND o.id <> m.id)
                   AS earlier
        FROM contact_messages m LEFT JOIN users u ON u.id = m.user_id
        WHERE m.id = :id
    """), {"id": message_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Message not found.", status_code=404)
    replies = (await session.execute(text("""
        SELECT r.id, coalesce(u.full_name, 'EduZone') AS author_name, r.body, r.created_at
        FROM contact_replies r LEFT JOIN users u ON u.id = r.author_id
        WHERE r.message_id = :id ORDER BY r.created_at
    """), {"id": message_id})).all()
    return ContactDetail(
        id=r.id, reference=r.reference, name=r.name, email=r.email, phone=r.phone, topic=r.topic,
        subject=r.subject, message=r.message, status=r.status, staff_note=r.staff_note, user_id=r.user_id,
        user_name=r.user_name, ip=r.ip_text, user_agent=r.user_agent, created_at=r.created_at,
        updated_at=r.updated_at, reply_list=[_pick(ContactReply, x) for x in replies], earlier=r.earlier,
    )


async def reply(session: AsyncSession, actor: PlatformActor, message_id: UUID, body: ReplyIn,
                emails: EmailSender) -> ContactDetail:
    msg = await get_message(session, message_id, mark_open=False)
    text_body = body.body.strip()
    if len(text_body) < 2:
        raise ApiError("VALIDATION_ERROR", "Write a reply first.", status_code=422)
    status: ContactStatus = "closed" if body.close else "replied"
    reply_id = (await session.execute(text("""
        INSERT INTO contact_replies (message_id, author_id, body) VALUES (:m, :a, :b) RETURNING id
    """), {"m": message_id, "a": actor.user_id, "b": text_body})).scalar_one()
    await session.execute(text("""
        UPDATE contact_messages SET status = :st, last_reply_at = now(), updated_at = now() WHERE id = :id
    """), {"st": status, "id": message_id})
    await _audit(session, actor, "platform.contact.reply", "contact_message", message_id,
                 {"reference": msg.reference, "reply_id": str(reply_id), "status": status})
    await _send(emails, msg.email, f"Re: {msg.subject} [{msg.reference}]", "\n".join([
        text_body,
        "",
        "The EduZone team",
        "",
        f"On {msg.created_at:%d %b %Y}, you wrote:",
        _quote(msg.message),
    ]), reply_to=get_settings().support_inbox_email)
    return await get_message(session, message_id, mark_open=False)


async def update(session: AsyncSession, actor: PlatformActor, message_id: UUID, body: ContactUpdate) -> ContactDetail:
    current = await get_message(session, message_id, mark_open=False)
    changes = {k: v for k, v in body.model_dump(exclude_unset=True).items()}
    if "status" in changes and changes["status"] is None:
        raise ApiError("VALIDATION_ERROR", "Status can't be empty.", status_code=422)
    if "staff_note" in changes:
        changes["staff_note"] = (changes["staff_note"] or "").strip() or None
    changes = {k: v for k, v in changes.items() if getattr(current, k) != v}
    if changes:
        sets = ", ".join(f"{k} = :{k}" for k in changes)
        await session.execute(text(f"UPDATE contact_messages SET {sets}, updated_at = now() WHERE id = :id"),
                              {**changes, "id": message_id})
        await _audit(session, actor, "platform.contact.update", "contact_message", message_id,
                     {"reference": current.reference, "changes": changes})
    return await get_message(session, message_id, mark_open=False)
