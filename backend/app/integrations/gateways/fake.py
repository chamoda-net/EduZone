"""A stand-in gateway for local development and tests (never enabled outside ENVIRONMENT=local).

Checkout sends the browser to a small page served by our own API (/api/v1/dev/fake-gateway/...)
with "Pay" and "Fail" buttons. Pressing one posts a signed notification to our webhook, exactly
like a real gateway would, then sends the browser back to the return URL.
"""

import hashlib
import hmac
import secrets
from urllib.parse import urlencode

from app.integrations.gateways.base import (
    CheckoutRedirect,
    CheckoutRequest,
    EventStatus,
    GatewayEvent,
    format_amount,
    parse_amount_cents,
)


class FakeGateway:
    name = "fake"

    def __init__(self, secret: str, api_base_url: str) -> None:
        self._secret = secret.encode()
        self._page = f"{api_base_url}/api/v1/dev/fake-gateway"

    def sign(self, fields: dict[str, str]) -> str:
        msg = "|".join(fields.get(k, "") for k in ("event_id", "order_id", "status", "amount", "currency"))
        return hmac.new(self._secret, msg.encode(), hashlib.sha256).hexdigest()

    def notification(self, order_id: str, status: EventStatus, amount_cents: int, currency: str) -> dict[str, str]:
        """What the fake gateway posts to our webhook."""
        fields = {"event_id": secrets.token_hex(8), "order_id": order_id, "status": status,
                  "amount": format_amount(amount_cents), "currency": currency, "card_no": "************4242",
                  "method": "visa", "payment_id": f"FAKE-{secrets.token_hex(5).upper()}"}
        return {**fields, "sig": self.sign(fields)}

    def create_checkout(self, req: CheckoutRequest) -> CheckoutRedirect:
        query = urlencode({"return_url": req.return_url, "cancel_url": req.cancel_url,
                           "description": req.description})
        return CheckoutRedirect(method="GET", url=f"{self._page}/{req.payment_key}?{query}")

    def verify_webhook(self, form: dict[str, str]) -> GatewayEvent:
        status = form.get("status", "")
        known: tuple[EventStatus, ...] = ("succeeded", "failed", "cancelled", "pending", "chargeback")
        card = form.get("card_no", "")
        return GatewayEvent(
            gateway=self.name,
            event_ref=f"fake:{form.get('event_id', '')}",
            payment_key=form.get("order_id", ""),
            status=status if status in known else "unknown",  # type: ignore[arg-type]
            amount_cents=parse_amount_cents(form.get("amount")),
            currency=form.get("currency"),
            gateway_payment_ref=form.get("payment_id"),
            method=form.get("method"),
            card_last4=card[-4:] if card[-4:].isdigit() else None,
            signature_ok=hmac.compare_digest(self.sign(form), form.get("sig", "")),
            raw=dict(form),
        )
