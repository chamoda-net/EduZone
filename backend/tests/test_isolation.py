"""Tenant isolation (CLAUDE.md section 5).

The structural test covers every tenant-scoped table, including ones added later.
Behavioural tests cover the tables seeded so far; each module adds its own tables'
isolation tests as it starts using them.
"""

from uuid import UUID

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.db import AdminSession
from app.core.tenancy import tenant_transaction
from tests.conftest import Seed


async def test_every_tenant_table_has_forced_rls_policy() -> None:
    async with AdminSession() as session:
        rows = (await session.execute(text("""
            SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
                   EXISTS (SELECT 1 FROM pg_policy p WHERE p.polrelid = c.oid) AS has_policy
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id' AND NOT a.attisdropped
            WHERE n.nspname = 'public' AND c.relkind = 'r'
        """))).all()
    assert len(rows) >= 19  # user_sessions became per account in 0005
    unprotected = [r.relname for r in rows if not (r.relrowsecurity and r.relforcerowsecurity and r.has_policy)]
    assert unprotected == []


@pytest.mark.parametrize(("table", "attr"), [("tenants", "id"), ("tenant_members", "member_id"),
                                             ("classes", "class_id")])
async def test_reads_see_only_own_tenant(seed: Seed, table: str, attr: str) -> None:
    ids = [getattr(seed.a, attr), getattr(seed.b, attr)]
    async with tenant_transaction(seed.a.id) as session:
        seen = (await session.execute(
            text(f"SELECT id FROM {table} WHERE id = ANY(:ids)"), {"ids": ids}
        )).scalars().all()
    assert seen == [getattr(seed.a, attr)]


@pytest.mark.parametrize(("table", "attr"), [("tenant_members", "member_id"), ("classes", "class_id")])
async def test_updates_and_deletes_cannot_reach_other_tenant(seed: Seed, table: str, attr: str) -> None:
    other: UUID = getattr(seed.b, attr)
    async with tenant_transaction(seed.a.id) as session:
        updated = await session.execute(
            text(f"UPDATE {table} SET updated_at = now() WHERE id = :id"), {"id": other}
        )
        deleted = await session.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": other})
    assert updated.rowcount == 0  # type: ignore[attr-defined]
    assert deleted.rowcount == 0  # type: ignore[attr-defined]


async def test_composite_fk_blocks_cross_tenant_link_even_for_admin(seed: Seed) -> None:
    # Admin bypasses RLS; the (tenant_id, id) foreign key still refuses a class in
    # tenant A taught by a member of tenant B.
    with pytest.raises(IntegrityError, match="foreign key"):
        async with AdminSession() as session, session.begin():
            await session.execute(
                text("INSERT INTO classes (tenant_id, teacher_member_id, title, slug, pricing_model) "
                     "VALUES (:t, :m, 'x', 'cross', 'free')"),
                {"t": seed.a.id, "m": seed.b.member_id},
            )
