from typing import Annotated

from fastapi import APIRouter, Query

from app.core.tenancy import TenantSession
from app.modules.auth.dependencies import StaffActor
from app.modules.ledger import service
from app.modules.ledger.schemas import Cashflow, Earnings

org_router = APIRouter(tags=["org: money"])

Month = Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}$", examples=["2026-10"])]


@org_router.get("/cashflow", response_model=Cashflow)
async def cashflow(session: TenantSession, actor: StaffActor,
                   from_: Annotated[str | None, Query(alias="from", pattern=r"^\d{4}-\d{2}$")] = None,
                   to: Month = None) -> Cashflow:
    """Monthly cash flow from the ledger (owners and admins). Default: the last 12 months."""
    return await service.cashflow(session, actor, start=service.parse_month(from_, "from"),
                                  end=service.parse_month(to, "to"))


@org_router.get("/earnings", response_model=Earnings)
async def earnings(session: TenantSession, actor: StaffActor, month: Month = None) -> Earnings:
    """Net per teacher for one month. Teachers see only their own line."""
    return await service.earnings(session, actor, month=service.parse_month(month, "month"))
