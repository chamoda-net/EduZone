"""The local platform admins and their authenticator codes right now, as JSON, for the development panel (tools/panel).

    python scripts/dev_admin_codes.py

Development only: refuses unless ENVIRONMENT=local and the database is on this computer. Prints codes, never secrets.
A code works once; when the current one was used, `code` is already the next one (sign-in accepts it early).
"""

import asyncio
import json
import time
from urllib.parse import urlsplit

from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import AdminSession, dispose_engines
from app.modules.platform import totp

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def refuse_unless_local() -> None:
    s = get_settings()
    if s.environment != "local":
        raise SystemExit("dev_admin_codes.py runs only with ENVIRONMENT=local")
    if urlsplit(s.admin_database_url).hostname not in LOCAL_HOSTS:
        raise SystemExit("dev_admin_codes.py runs only against a database on this computer")


async def codes() -> list[dict[str, object]]:
    async with AdminSession() as s:
        rows = (await s.execute(text("""
            SELECT u.full_name, u.phone, p.totp_secret, p.last_totp_step
            FROM platform_admins p JOIN users u ON u.id = p.user_id
            WHERE u.is_platform_admin AND u.phone IS NOT NULL ORDER BY u.created_at LIMIT 10
        """))).all()
    # Interrupted test runs leave admins named like the test fixture's: shown only when there is nobody else.
    rows = [r for r in rows if r.full_name != "EduZone Staff"] or rows
    now = totp.current_step()
    out: list[dict[str, object]] = []
    for r in rows:
        step = max(now, r.last_totp_step + 1)           # the first one that still works
        out.append({"name": r.full_name, "phone": r.phone,
                    "code": totp.code_at(r.totp_secret, step) if step <= now + 1 else None,
                    "valid_until": (max(step, now) + 2) * totp.STEP_SECONDS * 1000})
    return out


async def main() -> None:
    refuse_unless_local()
    try:
        print(json.dumps({"at": int(time.time() * 1000), "admins": await codes()}))
    finally:
        await dispose_engines()


if __name__ == "__main__":
    asyncio.run(main())
