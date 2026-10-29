from app.core.config import get_settings
from app.core.errors import ApiError
from app.integrations.gateways.base import Gateway
from app.integrations.gateways.fake import FakeGateway
from app.integrations.gateways.payhere import PayHereGateway


def get_gateway(name: str | None = None) -> Gateway:
    """The configured gateway (or a named one, for webhooks). FastAPI dependency too."""
    s = get_settings()
    name = name or s.payment_gateway
    if name == "payhere" and s.payhere_merchant_id and s.payhere_merchant_secret:
        return PayHereGateway(s.payhere_merchant_id, s.payhere_merchant_secret, s.payhere_sandbox)
    if name == "fake" and s.environment == "local":
        return FakeGateway(s.jwt_secret, s.api_public_url)
    raise ApiError("PAYMENTS_NOT_CONFIGURED", "Online payment is not set up yet.", status_code=503)


__all__ = ["Gateway", "get_gateway"]
