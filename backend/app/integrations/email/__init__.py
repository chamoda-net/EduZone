import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings

logger = logging.getLogger("eduzone.email")


class EmailSender(Protocol):
    """One interface for every email provider. Plain text for now (links and codes only)."""

    async def send(self, to: str, subject: str, body: str) -> None: ...


class ConsoleEmailSender:
    """Local development only: writes the email to the log instead of sending it."""

    async def send(self, to: str, subject: str, body: str) -> None:
        logger.warning("Email to %s: %s\n%s", to, subject, body)


class FileEmailSender:
    """Local development and browser tests only: appends each email as one JSON line."""

    def __init__(self, path: Path) -> None:
        self.path = path

    async def send(self, to: str, subject: str, body: str) -> None:
        line = json.dumps({"to": to, "subject": subject, "body": body, "at": datetime.now(UTC).isoformat()})
        await asyncio.to_thread(self._append, line)

    def _append(self, line: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def get_email_sender() -> EmailSender:
    """FastAPI dependency (tests override it to capture messages)."""
    settings = get_settings()
    if settings.email_provider == "console":
        return ConsoleEmailSender()
    if settings.email_provider == "file" and settings.environment == "local":
        return FileEmailSender(settings.email_outbox_path)
    raise RuntimeError(f"Email provider {settings.email_provider!r} is not available in ENVIRONMENT={settings.environment}")


__all__ = ["EmailSender", "get_email_sender"]
