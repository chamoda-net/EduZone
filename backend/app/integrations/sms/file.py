import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path


class FileSmsSender:
    """Local development and browser tests only: appends each message as one JSON line
    to an outbox file, so end-to-end tests can read the OTP code."""

    def __init__(self, path: Path) -> None:
        self.path = path

    async def send(self, phone: str, message: str) -> None:
        line = json.dumps({"phone": phone, "message": message, "at": datetime.now(UTC).isoformat()})
        await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
