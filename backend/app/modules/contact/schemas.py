from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.auth.phone import normalize_phone

Topic = Literal["classes", "payments", "account", "teaching", "institutes", "courses", "partnership", "other"]
ContactStatus = Literal["new", "open", "replied", "closed"]


class ContactIn(BaseModel):
    """A message from the Contact page. `website` is a honeypot: people never see it, so a value means a bot."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=120)
    email: EmailStr = Field(max_length=254)
    phone: str | None = Field(default=None, max_length=20)
    topic: Topic
    subject: str = Field(min_length=3, max_length=150)
    message: str = Field(min_length=10, max_length=5000)
    website: str | None = Field(default=None, max_length=200)

    @field_validator("name", "subject", "message")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Too short.")
        return v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        v = (v or "").strip()
        return normalize_phone(v) if v else None


class ContactSent(BaseModel):
    reference: str


# --- the support inbox (platform admin) -----------------------------------------------------------

class ContactRow(BaseModel):
    id: UUID
    reference: str
    name: str
    email: str
    topic: Topic
    subject: str
    preview: str
    status: ContactStatus
    signed_in: bool
    replies: int
    created_at: datetime
    last_reply_at: datetime | None


class ContactCounts(BaseModel):
    new: int
    open: int
    replied: int
    closed: int


class ContactPage(BaseModel):
    items: list[ContactRow]
    next_cursor: str | None
    counts: ContactCounts


class ContactReply(BaseModel):
    id: UUID
    author_name: str
    body: str
    created_at: datetime


class ContactDetail(BaseModel):
    id: UUID
    reference: str
    name: str
    email: str
    phone: str | None
    topic: Topic
    subject: str
    message: str
    status: ContactStatus
    staff_note: str | None
    user_id: UUID | None
    user_name: str | None
    ip: str | None
    user_agent: str | None
    created_at: datetime
    updated_at: datetime
    reply_list: list[ContactReply]
    earlier: int  # other messages from the same email address


class ReplyIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=2, max_length=10000)
    close: bool = False


class ContactUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ContactStatus | None = None
    staff_note: str | None = Field(default=None, max_length=2000)
