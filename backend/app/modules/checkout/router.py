import html
from typing import Annotated
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import AppSession
from app.core.errors import ApiError
from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.core.tenancy import TenantSession, request_host, tenant_transaction
from app.integrations.gateways import Gateway, get_gateway
from app.integrations.gateways.base import format_amount
from app.integrations.gateways.fake import FakeGateway
from app.modules.auth.dependencies import CurrentMember, StaffActor
from app.modules.checkout import service
from app.modules.checkout.schemas import CheckoutCreate, CheckoutOut, OrderOut, OrgOrderPage

PaymentGateway = Annotated[Gateway, Depends(get_gateway)]

student_router = APIRouter(prefix="/student", tags=["student: payments"])


@student_router.post("/checkout", response_model=CheckoutOut, status_code=201)
async def checkout(body: CheckoutCreate, request: Request, session: TenantSession, auth: CurrentMember,
                   gateway: PaymentGateway) -> CheckoutOut:
    return await service.create_checkout(session, auth, request_host(request), body, gateway)


@student_router.get("/orders", response_model=list[OrderOut])
async def my_orders(session: TenantSession, auth: CurrentMember) -> list[OrderOut]:
    return await service.my_orders(session, auth)


@student_router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: UUID, session: TenantSession, auth: CurrentMember) -> OrderOut:
    """Polled by the return page. Only the webhook ever marks an order paid."""
    return await service.get_order(session, auth, order_id)


org_router = APIRouter(tags=["org: payments"])


@org_router.get("/orders", response_model=OrgOrderPage)
async def org_orders(
    session: TenantSession, actor: StaffActor,
    status: str | None = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> OrgOrderPage:
    return await service.org_orders(session, actor, status=status, cursor=cursor, limit=limit)


# --- gateway notifications (no tenant host; see CLAUDE.md section 5) ---------------------

webhook_router = APIRouter(prefix="/webhooks", tags=["webhooks"])


async def _notify(gateway: str, request: Request) -> JSONResponse:
    form = {k: str(v) for k, v in (await request.form()).items()}
    try:
        outcome = await service.process_notification(gateway, form)
    except service.WebhookRejected:
        return JSONResponse({"ok": False}, status_code=400)
    except ApiError as exc:
        if exc.code == "PAYMENTS_NOT_CONFIGURED":
            return JSONResponse({"ok": False}, status_code=404)
        raise
    return JSONResponse({"ok": True, "outcome": outcome})


@webhook_router.post("/payhere")
async def payhere_notify(request: Request) -> JSONResponse:
    return await _notify("payhere", request)


@webhook_router.post("/fake")
async def fake_notify(request: Request) -> JSONResponse:
    return await _notify("fake", request)


# --- local development only: a pretend gateway page ------------------------------------------

dev_router = APIRouter(prefix="/dev", tags=["dev"], include_in_schema=False)


def _fake() -> FakeGateway:
    s = get_settings()
    if s.environment != "local":
        raise ApiError("NOT_FOUND", "Not found.", status_code=404)
    gw = get_gateway("fake")
    assert isinstance(gw, FakeGateway)
    return gw


def _local_url(url: str) -> str:
    """Only send the browser back to a local site (this page must not become an open redirect)."""
    host = urlparse(url).hostname or ""
    if host != "localhost" and not host.endswith(".localhost"):
        raise ApiError("BAD_REQUEST", "Bad return URL.", status_code=400)
    return url


async def _payment(key: str) -> tuple[int, str]:
    async with AppSession() as s:
        tenant_id = (await s.execute(text("SELECT resolve_payment_tenant('fake', :k)"), {"k": key})).scalar_one()
    if tenant_id is None:
        raise ApiError("NOT_FOUND", "Unknown payment.", status_code=404)
    async with tenant_transaction(tenant_id) as session:
        p = (await session.execute(text("""
            SELECT o.total_cents, o.currency FROM payments p JOIN orders o ON o.id = p.order_id
            WHERE p.gateway = 'fake' AND p.idempotency_key = :k
        """), {"k": key})).one()
    return p.total_cents, p.currency


@dev_router.get("/fake-gateway/{key}", response_class=HTMLResponse)
async def fake_gateway_page(key: str, return_url: str, cancel_url: str, description: str = "") -> HTMLResponse:
    _fake()
    amount, currency = await _payment(key)
    e = html.escape
    page = f"""<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Test gateway</title><style>body{{font-family:system-ui;max-width:420px;margin:40px auto;padding:0 16px}}
button{{font-size:16px;padding:12px 18px;margin:6px 6px 0 0;border-radius:8px;border:1px solid #888;cursor:pointer}}
.pay{{background:#1e8e3e;color:#fff;border:0}}</style></head><body>
<p style="color:#b26a00"><b>Test gateway</b>: local development only. No real money moves.</p>
<h2>{e(description)}</h2><p style="font-size:22px">{e(currency)} {format_amount(amount)}</p>
<form method="post"><input type="hidden" name="return_url" value="{e(return_url)}">
<input type="hidden" name="cancel_url" value="{e(cancel_url)}">
<button class="pay" name="outcome" value="succeeded">Pay</button>
<button name="outcome" value="failed">Card declined</button>
<button name="outcome" value="cancelled">Cancel</button></form></body></html>"""
    return HTMLResponse(page)


@dev_router.post("/fake-gateway/{key}")
async def fake_gateway_submit(key: str, outcome: Annotated[str, Form()], return_url: Annotated[str, Form()],
                              cancel_url: Annotated[str, Form()]) -> RedirectResponse:
    gw = _fake()
    back = _local_url(cancel_url if outcome == "cancelled" else return_url)
    amount, currency = await _payment(key)
    status = outcome if outcome in ("succeeded", "failed", "cancelled") else "failed"
    # Exactly what a real gateway does: a signed server-to-server notification.
    await service.process_notification("fake", gw.notification(key, status, amount, currency))  # type: ignore[arg-type]
    return RedirectResponse(back, status_code=303)
