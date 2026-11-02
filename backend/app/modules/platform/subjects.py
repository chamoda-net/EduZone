"""Subjects (migration phase 8). EduZone manages the list; each slug is a public URL (/physics), so it is fixed
once created and can never be a reserved route (the DB check uses is_reserved_slug()). Hiding a subject takes its
page and its classes off the marketplace (the public views join on subjects.is_active); nothing is deleted."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.platform.auth import PlatformActor
from app.modules.platform.schemas import SubjectCreate, SubjectRow, SubjectUpdate
from app.modules.platform.service import _audit

_SELECT = """
    SELECT s.id, s.slug, s.name, s.sort_order, s.is_active, s.created_at,
           (SELECT count(*) FROM classes c WHERE c.subject_id = s.id AND c.status = 'published') AS classes
    FROM subjects s
"""


def _row(r: Any) -> SubjectRow:
    return SubjectRow.model_validate({k: getattr(r, k) for k in SubjectRow.model_fields})


async def list_subjects(session: AsyncSession) -> list[SubjectRow]:
    rows = (await session.execute(text(_SELECT + " ORDER BY s.sort_order, s.name"))).all()
    return [_row(r) for r in rows]


async def _get(session: AsyncSession, subject_id: UUID) -> SubjectRow:
    r = (await session.execute(text(_SELECT + " WHERE s.id = :id"), {"id": subject_id})).one_or_none()
    if r is None:
        raise ApiError("NOT_FOUND", "Subject not found.", status_code=404)
    return _row(r)


async def create_subject(session: AsyncSession, actor: PlatformActor, body: SubjectCreate) -> SubjectRow:
    if (await session.execute(text("SELECT is_reserved_slug(:s)"), {"s": body.slug})).scalar_one():
        raise ApiError("SLUG_RESERVED", "That address is used by the site itself. Pick another.", status_code=422)
    try:
        async with session.begin_nested():
            subject_id = (await session.execute(text("""
                INSERT INTO subjects (slug, name, sort_order) VALUES (:slug, :name, :sort) RETURNING id
            """), {"slug": body.slug, "name": body.name.strip(), "sort": body.sort_order})).scalar_one()
    except IntegrityError as exc:
        raise ApiError("SLUG_TAKEN", "Another subject already uses this address.", status_code=409) from exc
    await _audit(session, actor, "platform.subject.create", "subject", subject_id,
                 {"slug": body.slug, "name": body.name})
    return await _get(session, subject_id)


async def update_subject(session: AsyncSession, actor: PlatformActor, subject_id: UUID,
                         body: SubjectUpdate) -> SubjectRow:
    current = await _get(session, subject_id)
    changes = {k: (v.strip() if isinstance(v, str) else v) for k, v in body.changes().items()}
    changes = {k: v for k, v in changes.items() if getattr(current, k) != v}
    if changes:
        sets = ", ".join(f"{k} = :{k}" for k in changes)
        await session.execute(text(f"UPDATE subjects SET {sets} WHERE id = :id"), {**changes, "id": subject_id})
        if set(changes) == {"is_active"}:
            action = "platform.subject.show" if changes["is_active"] else "platform.subject.hide"
        else:
            action = "platform.subject.update"
        await _audit(session, actor, action, "subject", subject_id, {"changes": changes})
    return await _get(session, subject_id)
