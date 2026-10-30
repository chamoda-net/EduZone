"""Catalogue DB access. Always called inside a tenant transaction: RLS scopes every query,
and inserts take tenant_id from current_tenant_id(), never from the client."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, exists, func, insert, literal, select, text, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.catalog.models import ClassModel, ClassMonth, Lesson

_REFRESH = {"populate_existing": True}


async def get_currency(session: AsyncSession) -> str:
    return (await session.execute(text("SELECT currency FROM tenants WHERE id = current_tenant_id()"))).scalar_one()


async def get_member(session: AsyncSession, member_id: UUID) -> Any:
    return (await session.execute(
        text("SELECT role, status FROM tenant_members WHERE id = :id"), {"id": member_id}
    )).one_or_none()


# --- classes --------------------------------------------------------------------------

async def list_classes(
    session: AsyncSession, *, teacher_member_id: UUID | None, status: str | None,
    after: tuple[datetime, UUID] | None, limit: int,
) -> list[ClassModel]:
    q = select(ClassModel).order_by(ClassModel.created_at.desc(), ClassModel.id.desc()).limit(limit)
    if teacher_member_id is not None:
        q = q.where(ClassModel.teacher_member_id == teacher_member_id)
    if status is not None:
        q = q.where(ClassModel.status == status)
    if after is not None:
        # Typed literals: an untyped datetime would bind as timestamp *without* time zone.
        q = q.where(tuple_(ClassModel.created_at, ClassModel.id)
                    < tuple_(literal(after[0], ClassModel.created_at.type), literal(after[1], ClassModel.id.type)))
    return list((await session.scalars(q)).all())


async def get_class(session: AsyncSession, class_id: UUID, *, for_update: bool = False) -> ClassModel | None:
    q = select(ClassModel).where(ClassModel.id == class_id).execution_options(**_REFRESH)
    if for_update:
        q = q.with_for_update()
    return (await session.scalars(q)).one_or_none()


async def class_slug_taken(session: AsyncSession, slug: str, exclude_id: UUID | None = None) -> bool:
    conditions = [ClassModel.slug == slug]
    if exclude_id is not None:
        conditions.append(ClassModel.id != exclude_id)
    return bool((await session.execute(select(exists().where(*conditions)))).scalar())


async def class_has_content(session: AsyncSession, class_id: UUID) -> bool:
    q = select(
        exists().where(ClassMonth.class_id == class_id) | exists().where(Lesson.class_id == class_id)
    )
    return bool((await session.execute(q)).scalar())


async def insert_class(session: AsyncSession, values: dict[str, Any]) -> ClassModel:
    stmt = insert(ClassModel).values(tenant_id=func.current_tenant_id(), **values).returning(ClassModel)
    return (await session.scalars(stmt)).one()


async def update_class(session: AsyncSession, class_id: UUID, values: dict[str, Any]) -> ClassModel:
    stmt = (update(ClassModel).where(ClassModel.id == class_id).values(**values)
            .returning(ClassModel).execution_options(**_REFRESH))
    return (await session.scalars(stmt)).one()


async def delete_class(session: AsyncSession, class_id: UUID) -> None:
    await session.execute(delete(ClassModel).where(ClassModel.id == class_id))


# --- months ---------------------------------------------------------------------------

async def list_months(session: AsyncSession, class_id: UUID) -> list[ClassMonth]:
    q = select(ClassMonth).where(ClassMonth.class_id == class_id).order_by(ClassMonth.month_start)
    return list((await session.scalars(q)).all())


async def get_month(session: AsyncSession, month_id: UUID, *, for_update: bool = False) -> ClassMonth | None:
    q = select(ClassMonth).where(ClassMonth.id == month_id).execution_options(**_REFRESH)
    if for_update:
        q = q.with_for_update()
    return (await session.scalars(q)).one_or_none()


async def month_exists(session: AsyncSession, class_id: UUID, month_start: Any) -> bool:
    q = select(exists().where(ClassMonth.class_id == class_id, ClassMonth.month_start == month_start))
    return bool((await session.execute(q)).scalar())


async def month_has_lessons(session: AsyncSession, month_id: UUID) -> bool:
    return bool((await session.execute(select(exists().where(Lesson.class_month_id == month_id)))).scalar())


async def insert_month(session: AsyncSession, values: dict[str, Any]) -> ClassMonth:
    stmt = insert(ClassMonth).values(tenant_id=func.current_tenant_id(), **values).returning(ClassMonth)
    return (await session.scalars(stmt)).one()


async def update_month(session: AsyncSession, month_id: UUID, values: dict[str, Any]) -> ClassMonth:
    stmt = (update(ClassMonth).where(ClassMonth.id == month_id).values(**values)
            .returning(ClassMonth).execution_options(**_REFRESH))
    return (await session.scalars(stmt)).one()


async def delete_month(session: AsyncSession, month_id: UUID) -> None:
    await session.execute(delete(ClassMonth).where(ClassMonth.id == month_id))


# --- lessons --------------------------------------------------------------------------

async def list_lessons(session: AsyncSession, class_id: UUID, month_id: UUID | None) -> list[Lesson]:
    q = (select(Lesson).where(Lesson.class_id == class_id)
         .order_by(Lesson.class_month_id, Lesson.sort_order, Lesson.created_at))
    if month_id is not None:
        q = q.where(Lesson.class_month_id == month_id)
    return list((await session.scalars(q)).all())


async def get_lesson(session: AsyncSession, lesson_id: UUID, *, for_update: bool = False) -> Lesson | None:
    q = select(Lesson).where(Lesson.id == lesson_id).execution_options(**_REFRESH)
    if for_update:
        q = q.with_for_update()
    return (await session.scalars(q)).one_or_none()


async def insert_lesson(session: AsyncSession, values: dict[str, Any]) -> Lesson:
    stmt = insert(Lesson).values(tenant_id=func.current_tenant_id(), **values).returning(Lesson)
    return (await session.scalars(stmt)).one()


async def update_lesson(session: AsyncSession, lesson_id: UUID, values: dict[str, Any]) -> Lesson:
    stmt = (update(Lesson).where(Lesson.id == lesson_id).values(**values)
            .returning(Lesson).execution_options(**_REFRESH))
    return (await session.scalars(stmt)).one()


async def delete_lesson(session: AsyncSession, lesson_id: UUID) -> None:
    await session.execute(delete(Lesson).where(Lesson.id == lesson_id))


async def tenant_status(session: AsyncSession) -> str:
    return (await session.execute(text("SELECT status FROM tenants WHERE id = current_tenant_id()"))).scalar_one()
