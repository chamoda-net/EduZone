"""Media DB access. Always inside a tenant transaction (RLS scopes every query)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import exists, func, insert, literal, select, text, tuple_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.media.models import LessonResource, MediaAsset

_REFRESH = {"populate_existing": True}


async def tenant_media_settings(session: AsyncSession) -> Any:
    return (await session.execute(text(
        "SELECT id, bunny_library_id, storage_limit_bytes FROM tenants WHERE id = current_tenant_id()"
    ))).one()


async def resolve_library_tenant(session: AsyncSession, library_id: int) -> UUID | None:
    """No tenant context needed: SECURITY DEFINER lookup for the Bunny webhook."""
    return (await session.execute(
        text("SELECT resolve_bunny_library_tenant(:lib)"), {"lib": library_id}
    )).scalar_one()


async def stored_bytes(session: AsyncSession) -> int:
    q = select(func.coalesce(func.sum(MediaAsset.size_bytes), 0)).where(
        MediaAsset.status.notin_(("deleted", "failed"))
    )
    return int((await session.execute(q)).scalar_one())


async def insert_asset(session: AsyncSession, values: dict[str, Any]) -> MediaAsset:
    stmt = insert(MediaAsset).values(tenant_id=func.current_tenant_id(), **values).returning(MediaAsset)
    return (await session.scalars(stmt)).one()


async def get_asset(session: AsyncSession, asset_id: UUID, *, for_update: bool = False) -> MediaAsset | None:
    q = select(MediaAsset).where(MediaAsset.id == asset_id, MediaAsset.status != "deleted").execution_options(**_REFRESH)
    if for_update:
        q = q.with_for_update()
    return (await session.scalars(q)).one_or_none()


async def get_video_by_guid(session: AsyncSession, guid: str) -> MediaAsset | None:
    q = (select(MediaAsset)
         .where(MediaAsset.provider == "bunny_stream", MediaAsset.external_id == guid)
         .with_for_update().execution_options(**_REFRESH))
    return (await session.scalars(q)).one_or_none()


async def update_asset(session: AsyncSession, asset_id: UUID, values: dict[str, Any]) -> MediaAsset:
    stmt = (update(MediaAsset).where(MediaAsset.id == asset_id).values(**values)
            .returning(MediaAsset).execution_options(**_REFRESH))
    return (await session.scalars(stmt)).one()


async def list_assets(
    session: AsyncSession, *, uploaded_by: UUID | None, kind: str | None,
    after: tuple[datetime, UUID] | None, limit: int,
) -> list[MediaAsset]:
    q = (select(MediaAsset).where(MediaAsset.status != "deleted")
         .order_by(MediaAsset.created_at.desc(), MediaAsset.id.desc()).limit(limit))
    if uploaded_by is not None:
        q = q.where(MediaAsset.uploaded_by == uploaded_by)
    if kind is not None:
        q = q.where(MediaAsset.kind == kind)
    if after is not None:
        q = q.where(tuple_(MediaAsset.created_at, MediaAsset.id)
                    < tuple_(literal(after[0], MediaAsset.created_at.type), literal(after[1], MediaAsset.id.type)))
    return list((await session.scalars(q)).all())


async def asset_in_use(session: AsyncSession, asset_id: UUID) -> bool:
    return bool((await session.execute(select(exists().where(LessonResource.media_asset_id == asset_id)))).scalar())


# --- lesson resources ---------------------------------------------------------------

async def list_resources(session: AsyncSession, lesson_id: UUID) -> list[tuple[LessonResource, MediaAsset]]:
    q = (select(LessonResource, MediaAsset)
         .join(MediaAsset, MediaAsset.id == LessonResource.media_asset_id)
         .where(LessonResource.lesson_id == lesson_id)
         .order_by(LessonResource.sort_order, LessonResource.created_at))
    return [(r, m) for r, m in (await session.execute(q)).all()]


async def resource_exists(session: AsyncSession, lesson_id: UUID, asset_id: UUID) -> bool:
    q = select(exists().where(LessonResource.lesson_id == lesson_id, LessonResource.media_asset_id == asset_id))
    return bool((await session.execute(q)).scalar())


async def insert_resource(session: AsyncSession, values: dict[str, Any]) -> LessonResource:
    next_order = (select(func.coalesce(func.max(LessonResource.sort_order), 0) + 1)
                  .where(LessonResource.lesson_id == values["lesson_id"]).scalar_subquery())
    stmt = (insert(LessonResource)
            .values(tenant_id=func.current_tenant_id(), sort_order=next_order, **values)
            .returning(LessonResource))
    return (await session.scalars(stmt)).one()


async def get_resource(session: AsyncSession, resource_id: UUID) -> LessonResource | None:
    q = select(LessonResource).where(LessonResource.id == resource_id).with_for_update()
    return (await session.scalars(q)).one_or_none()


async def delete_resource(session: AsyncSession, resource_id: UUID) -> None:
    await session.execute(text("DELETE FROM lesson_resources WHERE id = :id"), {"id": resource_id})
