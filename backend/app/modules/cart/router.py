from uuid import UUID

from fastapi import APIRouter, Request

from app.core.tenancy import request_host
from app.modules.auth.dependencies import CurrentUser
from app.modules.cart import service
from app.modules.cart.schemas import Cart, CartItemIn, CartMerge, CheckoutDetail, CheckoutStarted
from app.modules.checkout.router import PaymentGateway

# The signed-in user's cart and checkouts, across every teacher.
router = APIRouter(prefix="/me", tags=["cart"])


@router.get("/cart", response_model=Cart)
async def get_cart(user: CurrentUser) -> Cart:
    return await service.get_cart(user)


@router.post("/cart/items", response_model=Cart, status_code=201)
async def add_item(body: CartItemIn, user: CurrentUser) -> Cart:
    return await service.add_item(user, body)


@router.delete("/cart/items/{item_id}", response_model=Cart)
async def remove_item(item_id: UUID, user: CurrentUser) -> Cart:
    return await service.remove_item(user, item_id)


@router.post("/cart/merge", response_model=Cart)
async def merge(body: CartMerge, user: CurrentUser) -> Cart:
    return await service.merge(user, body.items)


@router.post("/checkouts", response_model=CheckoutStarted, status_code=201)
async def start_checkout(request: Request, user: CurrentUser, gateway: PaymentGateway) -> CheckoutStarted:
    """Pay for the whole cart: one payment, one order per item in its teacher's organization."""
    return await service.start_checkout(user, request_host(request), gateway)


@router.get("/checkouts/{checkout_id}", response_model=CheckoutDetail)
async def get_checkout(checkout_id: UUID, user: CurrentUser) -> CheckoutDetail:
    return await service.get_checkout(user.user_id, checkout_id)


# A guest's cart lives in the browser; this prices it from the public marketplace data.
public_router = APIRouter(prefix="/market", tags=["cart"])


@public_router.post("/cart/preview", response_model=Cart)
async def preview(body: CartMerge) -> Cart:
    return await service.preview(body.items)
