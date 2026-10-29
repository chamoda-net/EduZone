"""audit_logs: every state-changing org/platform action writes one row (CLAUDE.md section 12)."""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def write_audit(
    session: AsyncSession,
    *,
    actor_user_id: UUID | None,           # None = the system (e.g. a gateway webhook)
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    details: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    """Tenant-scoped: tenant_id is the current tenant. Runs in the caller's transaction,
    so the audit row commits or rolls back together with the change it describes."""
    await session.execute(
        text("""
            INSERT INTO audit_logs (tenant_id, actor_user_id, action, entity_type, entity_id, details, ip_address)
            VALUES (current_tenant_id(), :actor, :action, :etype, :eid, CAST(:details AS jsonb), CAST(:ip AS inet))
        """),
        {
            "actor": actor_user_id, "action": action, "etype": entity_type, "eid": entity_id,
            "details": json.dumps(details, default=str) if details is not None else None, "ip": ip,
        },
    )
