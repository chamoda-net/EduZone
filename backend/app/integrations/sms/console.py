import logging

logger = logging.getLogger("eduzone.sms")


class ConsoleSmsSender:
    """Local development only: writes the message to the log instead of sending it."""

    async def send(self, phone: str, message: str) -> None:
        logger.warning("SMS to %s: %s", phone, message)
