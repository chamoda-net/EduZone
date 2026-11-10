"""Record commission changes whose date has come (docs/COURSES.md C.10). Checkout already uses them on their date
(commission_rate() counts due changes), so this only marks them applied and moves the rate into the default or the
override. Safe to run any time; meant for a daily job."""

import asyncio

from app.core.db import AdminSession, dispose_engines
from app.modules.platform.commission import apply_due


async def main() -> None:
    try:
        async with AdminSession() as session, session.begin():
            print(f"applied {await apply_due(session)} commission change(s)")
    finally:
        await dispose_engines()


if __name__ == "__main__":
    asyncio.run(main())
