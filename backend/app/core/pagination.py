"""Cursor pagination over (created_at DESC, id DESC). The cursor is opaque to clients."""

import base64
import json
from datetime import datetime
from uuid import UUID

from app.core.errors import ApiError

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def encode_cursor(created_at: datetime, row_id: UUID) -> str:
    raw = json.dumps([created_at.isoformat(), str(row_id)]).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        raw = base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4))
        created_at, row_id = json.loads(raw)
        return datetime.fromisoformat(created_at), UUID(row_id)
    except (ValueError, TypeError) as exc:
        raise ApiError("BAD_REQUEST", "Invalid cursor.", status_code=400) from exc
