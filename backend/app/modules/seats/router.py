from typing import Literal
from uuid import UUID

from fastapi import APIRouter

from app.core.tenancy import TenantSession
from app.modules.auth.dependencies import StaffActor
from app.modules.seats import requests, service
from app.modules.seats.schemas import KeepIn, SeatDecision, SeatRequestRow, SeatsOut

# Organization console: who has the seats of a class the caller manages.
org_router = APIRouter(tags=["org: seats"])


@org_router.get("/classes/{class_id}/seats", response_model=SeatsOut)
async def class_seats(class_id: UUID, session: TenantSession, actor: StaffActor,
                      month_id: UUID | None = None) -> SeatsOut:
    return await service.class_seats(session, actor, class_id, month_id)


@org_router.put("/months/{month_id}/seat-keeps/{member_id}", response_model=SeatsOut)
async def decide_keep(month_id: UUID, member_id: UUID, body: KeepIn, session: TenantSession,
                      actor: StaffActor) -> SeatsOut:
    return await service.decide_keep(session, actor, month_id, member_id, body)


@org_router.delete("/months/{month_id}/seat-keeps/{member_id}", response_model=SeatsOut)
async def clear_keep(month_id: UUID, member_id: UUID, session: TenantSession, actor: StaffActor,
                     allow_over_limit: bool = False) -> SeatsOut:
    return await service.clear_keep(session, actor, month_id, member_id, allow_over_limit=allow_over_limit)


@org_router.get("/seat-requests", response_model=list[SeatRequestRow])
async def seat_requests(session: TenantSession, actor: StaffActor,
                        status: Literal["pending", "approved", "rejected", "expired", "used"] = "pending",
                        ) -> list[SeatRequestRow]:
    return await requests.inbox(session, actor, status)


@org_router.post("/seat-requests/{request_id}/decision", response_model=SeatRequestRow)
async def decide_seat_request(request_id: UUID, body: SeatDecision, session: TenantSession,
                              actor: StaffActor) -> SeatRequestRow:
    return await requests.decide(session, actor, request_id, body)
