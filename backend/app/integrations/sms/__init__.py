from app.core.config import get_settings
from app.integrations.sms.base import SmsSender
from app.integrations.sms.console import ConsoleSmsSender
from app.integrations.sms.file import FileSmsSender


def get_sms_sender() -> SmsSender:
    """FastAPI dependency (tests override it to capture messages)."""
    settings = get_settings()
    provider = settings.sms_provider
    if provider == "console":
        return ConsoleSmsSender()
    if provider == "file" and settings.environment == "local":
        return FileSmsSender(settings.sms_outbox_path)
    raise RuntimeError(f"SMS provider {provider!r} is not available in ENVIRONMENT={settings.environment}")


__all__ = ["SmsSender", "get_sms_sender"]
