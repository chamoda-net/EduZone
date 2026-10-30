from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request, Response

from app.core.tenancy import request_host
from app.modules.auth.dependencies import CurrentUser
from app.modules.checkout import service as checkout
from app.modules.checkout.router import PaymentGateway
from app.modules.checkout.schemas import CheckoutCreate, CheckoutOut, OrderOut
from app.modules.learn import service
from app.modules.learn.schemas import MyRequest, Today, UpcomingLesson
from app.modules.learning import service as learning
from app.modules.learning.schemas import (
    LateRequestCreate,
    LateRequestOut,
    MyClass,
    OpenResourceOut,
    StudentClassView,
    StudentLessonDetail,
)

# The student area on any host: one account across every teacher. Lists span tenants; actions
# on a class, month, lesson, file or order run in that entity's own tenant (see service.py).
router = APIRouter(prefix="/learn", tags=["learn"])


@router.get("/today", response_model=Today)
async def today(user: CurrentUser) -> Today:
    return await service.today(user)


@router.get("/schedule", response_model=list[UpcomingLesson])
async def schedule(user: CurrentUser, days: Annotated[int, Query(ge=1, le=62)] = 30) -> list[UpcomingLesson]:
    return await service.schedule(user, days)


@router.get("/classes", response_model=list[MyClass])
async def my_classes(user: CurrentUser) -> list[MyClass]:
    return await service.my_classes(user)


@router.get("/requests", response_model=list[MyRequest])
async def my_requests(user: CurrentUser) -> list[MyRequest]:
    return await service.my_requests(user)


@router.get("/payments", response_model=list[OrderOut])
async def my_payments(user: CurrentUser) -> list[OrderOut]:
    return await service.my_payments(user)


@router.get("/classes/{class_id}", response_model=StudentClassView)
async def class_view(class_id: UUID, user: CurrentUser) -> StudentClassView:
    async with service.in_tenant_of("class", class_id, user) as (session, auth, org):
        view = await learning.class_view(session, auth, await service.class_slug(session, class_id))
    return view.model_copy(update={"klass": view.klass.model_copy(update={"org": org})})


@router.post("/classes/{class_id}/enroll", response_model=StudentClassView)
async def enroll(class_id: UUID, user: CurrentUser) -> StudentClassView:
    async with service.in_tenant_of("class", class_id, user) as (session, auth, org):
        view = await learning.enroll(session, auth, await service.class_slug(session, class_id))
    return view.model_copy(update={"klass": view.klass.model_copy(update={"org": org})})


@router.delete("/classes/{class_id}/enroll", status_code=204)
async def leave(class_id: UUID, user: CurrentUser) -> Response:
    async with service.in_tenant_of("class", class_id, user) as (session, auth, _):
        await learning.leave(session, auth, await service.class_slug(session, class_id))
    return Response(status_code=204)


@router.post("/months/{month_id}/late-request", response_model=LateRequestOut, status_code=201)
async def request_late_month(month_id: UUID, body: LateRequestCreate, user: CurrentUser) -> LateRequestOut:
    async with service.in_tenant_of("month", month_id, user) as (session, auth, _):
        return await learning.request_late_month(session, auth, month_id, body.note)


@router.get("/lessons/{lesson_id}", response_model=StudentLessonDetail)
async def lesson(lesson_id: UUID, user: CurrentUser) -> StudentLessonDetail:
    async with service.in_tenant_of("lesson", lesson_id, user) as (session, auth, org):
        detail = await learning.lesson_detail(session, auth, lesson_id)
    return detail.model_copy(update={"org": org})


@router.post("/resources/{resource_id}/open", response_model=OpenResourceOut)
async def open_resource(resource_id: UUID, user: CurrentUser) -> OpenResourceOut:
    async with service.in_tenant_of("resource", resource_id, user) as (session, auth, _):
        return await learning.open_resource(session, auth, resource_id)


@router.post("/checkout", response_model=CheckoutOut, status_code=201)
async def create_checkout(body: CheckoutCreate, request: Request, user: CurrentUser,
                          gateway: PaymentGateway) -> CheckoutOut:
    async with service.in_tenant_of("class", body.class_id, user) as (session, auth, _):
        return await checkout.create_checkout(session, auth, request_host(request), body, gateway)


@router.get("/orders/{order_id}", response_model=OrderOut)
async def get_order(order_id: UUID, user: CurrentUser) -> OrderOut:
    """Polled by the return page. Only the gateway's notification ever marks an order paid."""
    async with service.in_tenant_of("order", order_id, user) as (session, auth, org):
        order = await checkout.get_order(session, auth, order_id)
    return order.model_copy(update={"org": org})
