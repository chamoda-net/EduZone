"""The audit log (migration phase 8): every state-changing action by staff of an organization, EduZone staff and
the system, newest first. Read only; audit rows are never changed or deleted."""

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiError
from app.modules.platform.schemas import AuditPage, AuditRow


def _cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    try:
        return int(cursor)
    except ValueError as exc:
        raise ApiError("BAD_REQUEST", "Invalid cursor.", status_code=400) from exc


async def list_audit(session: AsyncSession, *, tenant_id: UUID | None, action: str | None, actor_id: UUID | None,
                     entity_id: UUID | None, cursor: str | None, limit: int) -> AuditPage:
    """`action` matches a prefix ('platform.' or 'platform.payout'). The cursor is the last row's id."""
    rows = (await session.execute(text("""
        SELECT a.id, a.created_at, a.tenant_id, t.name AS tenant_name, a.actor_user_id, u.full_name AS actor_name,
               a.action, a.entity_type, a.entity_id, a.details, host(a.ip_address) AS ip_address
        FROM audit_logs a
        LEFT JOIN tenants t ON t.id = a.tenant_id
        LEFT JOIN users u ON u.id = a.actor_user_id
        WHERE (CAST(:tid AS uuid) IS NULL OR a.tenant_id = :tid)
          AND (CAST(:act AS text) IS NULL OR a.action LIKE :act_like)
          AND (CAST(:actor AS uuid) IS NULL OR a.actor_user_id = :actor)
          AND (CAST(:eid AS uuid) IS NULL OR a.entity_id = :eid)
          AND (CAST(:after AS bigint) IS NULL OR a.id < :after)
        ORDER BY a.id DESC
        LIMIT :limit
    """), {"tid": tenant_id, "act": action, "act_like": _like_prefix(action), "actor": actor_id, "eid": entity_id,
           "after": _cursor(cursor), "limit": limit + 1})).all()
    page = rows[:limit]
    items: list[AuditRow] = [_row(r) for r in page]
    return AuditPage(items=items, next_cursor=str(page[-1].id) if len(rows) > limit else None)


def _like_prefix(action: str | None) -> str | None:
    if action is None:
        return None
    return action.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _row(r: Any) -> AuditRow:
    return AuditRow.model_validate({k: getattr(r, k) for k in AuditRow.model_fields})
