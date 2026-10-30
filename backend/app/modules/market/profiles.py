"""Teacher profiles: one public page identity per person, across every organization they teach for.

A profile is created automatically the first time a class of theirs is published (slug from their
name), and the teacher edits it from the console. Slugs are unique platform-wide.
"""

import re
import secrets
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_SLUG_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{1,38}[a-z0-9])$")


def slugify(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:34].strip("-")
    return base if len(base) >= 3 else f"teacher-{secrets.token_hex(3)}"


def valid_slug(slug: str) -> bool:
    return bool(_SLUG_RE.fullmatch(slug))


async def slug_taken(session: AsyncSession, slug: str, *, except_user: UUID | None = None) -> bool:
    return (await session.execute(text(
        "SELECT 1 FROM teacher_profiles WHERE slug = :s AND (CAST(:u AS uuid) IS NULL OR user_id <> :u)"
    ), {"s": slug, "u": except_user})).first() is not None


async def unique_slug(session: AsyncSession, name: str) -> str:
    base = slugify(name)
    candidate, n = base, 2
    while await slug_taken(session, candidate):
        candidate, n = f"{base}-{n}", n + 1
    return candidate


async def get_profile(session: AsyncSession, user_id: UUID) -> Any:
    return (await session.execute(text("""
        SELECT slug, display_name, headline, bio, photo_url, highlights FROM teacher_profiles WHERE user_id = :u
    """), {"u": user_id})).one_or_none()


async def ensure_for_user(session: AsyncSession, user_id: UUID, name: str) -> None:
    if await get_profile(session, user_id) is not None:
        return
    await session.execute(text("""
        INSERT INTO teacher_profiles (user_id, slug, display_name) VALUES (:u, :s, :n)
        ON CONFLICT (user_id) DO NOTHING
    """), {"u": user_id, "s": await unique_slug(session, name), "n": name[:80]})


async def ensure_for_member(session: AsyncSession, member_id: UUID) -> None:
    """In a tenant transaction: the profile of the member who teaches a class."""
    row = (await session.execute(text("""
        SELECT u.id, COALESCE(NULLIF(m.display_name, ''), u.full_name) AS name
        FROM tenant_members m JOIN users u ON u.id = m.user_id WHERE m.id = :m
    """), {"m": member_id})).one()
    await ensure_for_user(session, row.id, row.name)
