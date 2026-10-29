"""PayHere (Sri Lanka). Checkout is a form POST to PayHere; results arrive at notify_url.

Hash formulas follow PayHere's documentation; re-check them against the sandbox before launch.
"""

import hashlib
import hmac

from app.integrations.gateways.base import (
    CheckoutRedirect,
    CheckoutRequest,
    EventStatus,
    GatewayEvent,
    format_amount,
    parse_amount_cents,
)

_STATUS: dict[str, EventStatus] = {"2": "succeeded", "0": "pending", "-1": "cancelled", "-2": "failed",
                                   "-3": "chargeback"}


def _md5_upper(value: str) -> str:
    return hashlib.md5(value.encode()).hexdigest().upper()  # noqa: S324 - PayHere's scheme, not ours


class PayHereGateway:
    name = "payhere"

    def __init__(self, merchant_id: str, merchant_secret: str, sandbox: bool) -> None:
        self._merchant_id = merchant_id
        self._secret_hash = _md5_upper(merchant_secret)
        self._url = ("https://sandbox.payhere.lk/pay/checkout" if sandbox
                     else "https://www.payhere.lk/pay/checkout")

    def create_checkout(self, req: CheckoutRequest) -> CheckoutRedirect:
        amount = format_amount(req.amount_cents)
        digest = _md5_upper(f"{self._merchant_id}{req.payment_key}{amount}{req.currency}{self._secret_hash}")
        return CheckoutRedirect(method="POST", url=self._url, fields={
            "merchant_id": self._merchant_id,
            "return_url": req.return_url,
            "cancel_url": req.cancel_url,
            "notify_url": req.notify_url,
            "order_id": req.payment_key,
            "items": req.description[:100],
            "currency": req.currency,
            "amount": amount,
            "first_name": req.first_name,
            "last_name": req.last_name,
            "email": req.email,
            "phone": req.phone,
            "address": "-",
            "city": "-",
            "country": "Sri Lanka",
            "hash": digest,
        })

    def verify_webhook(self, form: dict[str, str]) -> GatewayEvent:
        g = form.get
        expected = _md5_upper(
            f"{g('merchant_id', '')}{g('order_id', '')}{g('payhere_amount', '')}{g('payhere_currency', '')}"
            f"{g('status_code', '')}{self._secret_hash}"
        )
        signature_ok = (g("merchant_id") == self._merchant_id
                        and hmac.compare_digest(expected, (g("md5sig") or "").upper()))
        card = g("card_no") or ""
        return GatewayEvent(
            gateway=self.name,
            event_ref=f"{g('payment_id', '')}:{g('status_code', '')}:{g('order_id', '')}",
            payment_key=g("order_id", ""),
            status=_STATUS.get(g("status_code", ""), "unknown"),
            amount_cents=parse_amount_cents(g("payhere_amount")),
            currency=g("payhere_currency"),
            gateway_payment_ref=g("payment_id"),
            method=(g("method") or "").lower() or None,
            card_last4=card[-4:] if len(card) >= 4 and card[-4:].isdigit() else None,
            signature_ok=signature_ok,
            raw=dict(form),
        )
