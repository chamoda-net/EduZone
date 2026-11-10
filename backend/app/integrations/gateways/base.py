"""One interface for every payment gateway (CLAUDE.md section 8). Checkout code never
imports a specific gateway; it asks `get_gateway()`."""

from dataclasses import dataclass, field
from typing import Literal, Protocol

EventStatus = Literal["succeeded", "failed", "cancelled", "pending", "chargeback", "unknown"]


@dataclass(frozen=True, slots=True)
class CheckoutRequest:
    payment_key: str              # payments.idempotency_key; the gateway echoes it back
    amount_cents: int
    currency: str
    description: str
    first_name: str
    last_name: str
    email: str
    phone: str
    return_url: str               # browser comes back here; it never grants access
    cancel_url: str
    notify_url: str               # server-to-server webhook


@dataclass(frozen=True, slots=True)
class CheckoutRedirect:
    """How the browser reaches the gateway: a form auto-submitted with these fields."""

    method: Literal["GET", "POST"]
    url: str
    fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class GatewayEvent:
    gateway: str
    event_ref: str                # unique per notification (idempotency of webhook storage)
    payment_key: str              # our payments.idempotency_key
    status: EventStatus
    amount_cents: int | None
    currency: str | None
    gateway_payment_ref: str | None
    method: str | None
    card_last4: str | None
    signature_ok: bool
    raw: dict[str, str]


@dataclass(frozen=True, slots=True)
class RefundResult:
    """processed: the gateway refunded it (ref = its refund id). manual: this gateway can't refund through its API
    (yet); staff refund in the gateway's portal and record it. failed: the gateway refused (message says why)."""

    status: Literal["processed", "manual", "failed"]
    ref: str | None = None
    message: str | None = None


class Gateway(Protocol):
    name: str

    def create_checkout(self, req: CheckoutRequest) -> CheckoutRedirect: ...

    def verify_webhook(self, form: dict[str, str]) -> GatewayEvent: ...

    async def refund(self, payment_ref: str, amount_cents: int, refund_key: str, reason: str) -> RefundResult:
        """Refund part or all of a payment. `refund_key` (our refunds.id) makes a repeat safe where the
        gateway supports it."""
        ...


def parse_amount_cents(value: str | None) -> int | None:
    """'2000.00' -> 200000 without floats. None for anything malformed."""
    if not value:
        return None
    whole, _, frac = value.strip().partition(".")
    if not whole.isdigit() or (frac and (not frac.isdigit() or len(frac) > 2)):
        return None
    return int(whole) * 100 + int(frac.ljust(2, "0") or 0)


def format_amount(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"
