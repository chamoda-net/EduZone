from typing import Protocol


class SmsSender(Protocol):
    """One interface for every SMS provider. `phone` is E.164."""

    async def send(self, phone: str, message: str) -> None: ...
