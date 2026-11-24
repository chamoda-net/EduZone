from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials

from app.core.pagination import DEFAULT_LIMIT, MAX_LIMIT
from app.integrations.email import EmailSender, get_email_sender
from app.modules.auth.dependencies import UserContext, _bearer, client_ip, current_user, user_agent
from app.modules.contact import service
from app.modules.contact.schemas import ContactDetail, ContactIn, ContactPage, ContactSent, ContactUpdate, ReplyIn
from app.modules.platform.auth import Admin, AdminTx

Emails = Annotated[EmailSender, Depends(get_email_sender)]


async def optional_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> UserContext | None:
    """The signed-in account when there is one; anyone may write to us."""
    return await current_user(credentials) if credentials is not None else None


# Public: the Contact page (any host, no sign-in needed).
public_router = APIRouter(prefix="/market", tags=["market"])


@public_router.post("/contact", response_model=ContactSent, status_code=202)
async def send_message(body: ContactIn, request: Request, emails: Emails,
                       user: Annotated[UserContext | None, Depends(optional_user)]) -> ContactSent:
    return await service.submit(body, user_id=user.user_id if user else None, ip=client_ip(request),
                                ua=user_agent(request), emails=emails)


# Platform admin: the support inbox.
admin_router = APIRouter(prefix="/platform/contact", tags=["platform"])


@admin_router.get("", response_model=ContactPage)
async def list_messages(
    actor: Admin, session: AdminTx,
    status: Literal["active", "new", "open", "replied", "closed"] | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
) -> ContactPage:
    return await service.list_messages(session, status=status, q=q, cursor=cursor, limit=limit)


@admin_router.get("/{message_id}", response_model=ContactDetail)
async def get_message(message_id: UUID, actor: Admin, session: AdminTx) -> ContactDetail:
    return await service.get_message(session, message_id)


@admin_router.post("/{message_id}/reply", response_model=ContactDetail)
async def reply(message_id: UUID, body: ReplyIn, actor: Admin, session: AdminTx, emails: Emails) -> ContactDetail:
    return await service.reply(session, actor, message_id, body, emails)


@admin_router.patch("/{message_id}", response_model=ContactDetail)
async def update(message_id: UUID, body: ContactUpdate, actor: Admin, session: AdminTx) -> ContactDetail:
    return await service.update(session, actor, message_id, body)
