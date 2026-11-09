"""The wishlist (docs/COURSES.md section C.8, step C5): courses a student saved for later.

Platform-level rows guarded by the user policy (migration 0014), like the cart. Only public courses can be saved;
a course that leaves the marketplace simply drops out of the list. Buying a course takes it off the wishlist
(cart.service.apply_checkout_event). Instructors see only how many saved a course (wishlist_count), never who.
"""

from uuid import UUID

from sqlalchemy import text

from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.tenancy import user_transaction
from app.modules.auth.dependencies import UserContext
from app.modules.market.courses import _CARD, _card
from app.modules.market.schemas import MarketCourse

MAX_ITEMS = 200


async def ids(user: UserContext) -> list[UUID]:
    async with user_transaction(user.user_id) as session:
        return list((await session.execute(text(
            "SELECT class_id FROM wishlist_items ORDER BY created_at DESC"))).scalars().all())


async def items(user: UserContext) -> list[MarketCourse]:
    saved = await ids(user)
    if not saved:
        return []
    async with AppSession() as session:
        rows = (await session.execute(text(f"SELECT {_CARD} FROM public_courses pc WHERE pc.id = ANY(:ids)"),
                                      {"ids": saved})).all()
    by_id = {r.id: _card(r) for r in rows}
    return [by_id[i] for i in saved if i in by_id]          # newest saved first


async def add(user: UserContext, course_id: UUID) -> list[UUID]:
    async with AppSession() as session:
        tenant_id = (await session.execute(text("SELECT tenant_id FROM public_courses WHERE id = :c"),
                                           {"c": course_id})).scalar_one_or_none()
    if tenant_id is None:
        raise ApiError("NOT_FOUND", "Course not found.", status_code=404)
    async with user_transaction(user.user_id) as session:
        count = (await session.execute(text("SELECT count(*) FROM wishlist_items"))).scalar_one()
        if count >= MAX_ITEMS:
            raise ApiError("WISHLIST_FULL", f"Your wishlist can hold up to {MAX_ITEMS} courses.", status_code=409)
        await session.execute(text("""
            INSERT INTO wishlist_items (user_id, tenant_id, class_id) VALUES (current_user_id(), :t, :c)
            ON CONFLICT (user_id, class_id) DO NOTHING
        """), {"t": tenant_id, "c": course_id})
    return await ids(user)


async def remove(user: UserContext, course_id: UUID) -> list[UUID]:
    async with user_transaction(user.user_id) as session:
        await session.execute(text("DELETE FROM wishlist_items WHERE class_id = :c"), {"c": course_id})
    return await ids(user)
