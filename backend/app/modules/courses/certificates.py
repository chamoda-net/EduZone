"""Certificates of completion (docs/COURSES.md section C.6, step C4).

Issued once a student completes every published lecture of a **paid** course (they bought it: a `purchase` grant
whose order item cost more than nothing). Free courses, courses given by the teacher and, later, 100% coupons get
no certificate. The row snapshots the names, title and length at issue time, so later edits don't change it.
Anyone can check a certificate at /certificates/<no> (verify_certificate(): snapshot fields and status only) and
download its PDF. A refund revokes it (step C6).
"""

import io
import secrets
from datetime import UTC
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.tenancy import tenant_transaction
from app.modules.auth.dependencies import UserContext
from app.modules.courses.schemas import CertificateOut, CertificateVerify
from app.modules.learning.access import ACTIVE_GRANT

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0/O or 1/I


def new_number() -> str:
    part = lambda: "".join(secrets.choice(_ALPHABET) for _ in range(4))  # noqa: E731
    return f"EZCERT-{part()}-{part()}"


async def maybe_issue(session: AsyncSession, member_id: UUID, course_id: UUID) -> str | None:
    """In the course's tenant transaction, after a lecture is completed: issue the certificate if this was the
    last one and the course was bought. Returns the number when one was issued."""
    row = (await session.execute(text(f"""
        SELECT c.id, c.kind, c.title, c.total_video_seconds,
               COALESCE(NULLIF(tm.display_name, ''), u.full_name) AS instructor_name,
               (SELECT count(*) FROM lessons l WHERE l.class_id = c.id AND l.section_id IS NOT NULL AND l.is_published)
                   AS total,
               (SELECT count(*) FROM lessons l JOIN lesson_completions lc ON lc.lesson_id = l.id
                WHERE l.class_id = c.id AND l.section_id IS NOT NULL AND l.is_published
                  AND lc.student_member_id = :m) AS done,
               EXISTS (SELECT 1 FROM access_grants g JOIN order_items i ON i.id = g.order_item_id
                       WHERE g.class_id = c.id AND g.class_month_id IS NULL AND g.student_member_id = :m
                         AND g.source = 'purchase' AND i.amount_cents > 0 AND {ACTIVE_GRANT}) AS paid,
               EXISTS (SELECT 1 FROM certificates x WHERE x.class_id = c.id AND x.student_member_id = :m
                       AND x.revoked_at IS NULL) AS has_certificate
        FROM classes c
        JOIN tenant_members tm ON tm.id = c.teacher_member_id
        JOIN users u ON u.id = tm.user_id
        WHERE c.id = :c
    """), {"c": course_id, "m": member_id})).one_or_none()
    if row is None or row.kind != "course" or row.has_certificate or not row.paid or row.total == 0:
        return None
    if row.done < row.total:
        return None
    student = (await session.execute(text(
        "SELECT u.full_name FROM tenant_members m JOIN users u ON u.id = m.user_id WHERE m.id = :m"),
        {"m": member_id})).scalar_one()
    for _ in range(5):
        number = new_number()
        try:
            async with session.begin_nested():
                await session.execute(text("""
                    INSERT INTO certificates (class_id, student_member_id, certificate_no, student_name, course_title,
                                              instructor_name, total_video_seconds)
                    VALUES (:c, :m, :no, :student, :title, :instructor, :secs)
                """), {"c": course_id, "m": member_id, "no": number, "student": student, "title": row.title,
                       "instructor": row.instructor_name, "secs": row.total_video_seconds})
            return number
        except IntegrityError:
            # A number clash (retry) or a certificate issued meanwhile by a parallel request (stop).
            if (await session.execute(text("""SELECT 1 FROM certificates WHERE class_id = :c AND student_member_id = :m
                                               AND revoked_at IS NULL"""), {"c": course_id, "m": member_id})).first():
                return None
    raise RuntimeError("could not find a free certificate number")


async def certificate_for(session: AsyncSession, member_id: UUID | None, course_id: UUID) -> str | None:
    if member_id is None:
        return None
    return (await session.execute(text("""
        SELECT certificate_no FROM certificates WHERE class_id = :c AND student_member_id = :m AND revoked_at IS NULL
    """), {"c": course_id, "m": member_id})).scalar_one_or_none()


async def my_certificates(user: UserContext, memberships: list[Any]) -> list[CertificateOut]:
    out: list[CertificateOut] = []
    for m in memberships:
        async with tenant_transaction(m.tenant_id) as session:
            rows = (await session.execute(text("""
                SELECT certificate_no, class_id AS course_id, course_title, student_name, instructor_name,
                       total_video_seconds, issued_at, revoked_at
                FROM certificates WHERE student_member_id = :m ORDER BY issued_at DESC
            """), {"m": m.member_id})).all()
        out.extend(CertificateOut(**r._mapping, org_name=m.name, verify_path=f"/certificates/{r.certificate_no}")
                   for r in rows)
    return sorted(out, key=lambda c: c.issued_at, reverse=True)


async def verify(number: str) -> CertificateVerify:
    async with AppSession() as session:
        r = (await session.execute(text("SELECT * FROM verify_certificate(:no)"), {"no": number})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "No certificate has this number.", status_code=404)
    return CertificateVerify(**r._mapping, valid=r.revoked_at is None)


def _hours(seconds: int) -> str:
    """'45 minutes', '1 hour', '2.5 hours'."""
    if seconds < 3600:
        return f"{max(1, round(seconds / 60))} minutes"
    h = round(seconds / 3600, 1)
    return f"{h:g} hour" if h == 1 else f"{h:g} hours"


def render_pdf(c: CertificateVerify, verify_url: str) -> bytes:
    """A4 landscape, EduZone's forest green and gold, with a QR code to the verify page."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import qr
    from reportlab.graphics.shapes import Drawing
    from reportlab.lib.colors import HexColor
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.pdfgen import canvas

    green, gold, ink, muted = HexColor("#14422c"), HexColor("#c79a2e"), HexColor("#17251d"), HexColor("#5c6b62")
    width, height = landscape(A4)
    buf = io.BytesIO()
    pdf = canvas.Canvas(buf, pagesize=(width, height))
    pdf.setTitle(f"Certificate {c.certificate_no}")
    pdf.setAuthor("EduZone")

    pdf.setFillColor(HexColor("#fbf8f1"))
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.setStrokeColor(green)
    pdf.setLineWidth(10)
    pdf.rect(24, 24, width - 48, height - 48, stroke=1, fill=0)
    pdf.setStrokeColor(gold)
    pdf.setLineWidth(1.5)
    pdf.rect(38, 38, width - 76, height - 76, stroke=1, fill=0)

    pdf.setFillColor(green)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawCentredString(width / 2, height - 90, "EduZone")
    pdf.setFillColor(gold)
    pdf.setFont("Helvetica", 11)
    pdf.drawCentredString(width / 2, height - 108, "CERTIFICATE OF COMPLETION")

    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 13)
    pdf.drawCentredString(width / 2, height - 170, "This is to certify that")
    pdf.setFillColor(ink)
    pdf.setFont("Times-Bold", 36)
    pdf.drawCentredString(width / 2, height - 215, c.student_name)
    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 13)
    pdf.drawCentredString(width / 2, height - 255, "has successfully completed the course")
    pdf.setFillColor(green)
    title_size = 24 if len(c.course_title) <= 50 else 18
    pdf.setFont("Times-Bold", title_size)
    pdf.drawCentredString(width / 2, height - 292, c.course_title)
    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 12)
    pdf.drawCentredString(width / 2, height - 318,
                          f"taught by {c.instructor_name} · {c.org_name} · {_hours(c.total_video_seconds)} of video")

    issued = c.issued_at.astimezone(ZoneInfo("Asia/Colombo")) if c.issued_at.tzinfo else c.issued_at.replace(tzinfo=UTC)
    pdf.setFillColor(ink)
    pdf.setFont("Helvetica", 11)
    pdf.drawString(80, 110, f"Issued {issued.strftime('%d %B %Y')}")
    pdf.drawString(80, 92, f"Certificate no. {c.certificate_no}")
    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(80, 74, f"Verify at {verify_url}")

    code = qr.QrCodeWidget(verify_url)
    x0, y0, x1, y1 = code.getBounds()
    size = 92
    drawing = Drawing(size, size, transform=[size / (x1 - x0), 0, 0, size / (y1 - y0), 0, 0])
    drawing.add(code)
    renderPDF.draw(drawing, pdf, width - 80 - size, 62)

    pdf.showPage()
    pdf.save()
    return buf.getvalue()
