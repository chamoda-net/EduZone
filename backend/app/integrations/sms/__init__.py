from app.core.config import get_settings
from app.integrations.sms.base import SmsSender
from app.integrations.sms.console import ConsoleSmsSender


def get_sms_sender() -> SmsSender:
    """FastAPI dependency (tests override it to capture messages)."""
    provider = get_settings().sms_provider
    if provider == "console":
        return ConsoleSmsSender()
    raise RuntimeError(f"unknown SMS provider: {provider}")


__all__ = ["SmsSender", "get_sms_sender"]
