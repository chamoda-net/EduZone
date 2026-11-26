from datetime import date, datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

Registration = Literal["open", "ask", "closed"]


class Seat(BaseModel):
    """A taken seat and why."""

    member_id: UUID
    full_name: str
    phone: str | None
    kind: Literal["access", "paying", "accepted", "kept"]
    source: str | None                   # access: purchase | manual | free | scholarship
    since: datetime
    held_until: datetime | None          # when a payment, an accepted request or a kept seat ends


class Lapsed(BaseModel):
    """A student of the previous month without a seat in this one."""

    member_id: UUID
    full_name: str
    phone: str | None
    released: bool                       # staff released their seat


class SeatsOut(BaseModel):
    limit: int | None                    # None = no limit
    taken: int
    free: int | None                     # None = no limit
    over_by: int
    registration: Registration           # for new students, today
    seats: list[Seat]
    lapsed: list[Lapsed]
    waiting: int                         # students on the notify list


class SeatRequestInfo(BaseModel):
    """The student's own request for a seat."""

    status: Literal["pending", "approved", "rejected", "expired"]
    held_until: datetime | None          # approved: pay before this
    decision_note: str | None
    created_at: datetime


class SeatState(BaseModel):
    """A class (or one open month of it) as this student finds it."""

    limited: bool                        # seats are limited (said even when the numbers are hidden)
    limit: int | None                    # None: no limit, or the teacher hides the numbers
    left: int | None
    full: bool
    registration: Registration
    problem: Literal["CLASS_FULL", "REGISTRATION_CLOSED", "SEAT_REQUEST_REQUIRED"] | None   # None: they can pay or join
    paying_until: datetime | None        # a payment of theirs holds a seat
    kept_until: datetime | None          # renew before this to keep their seat
    request: SeatRequestInfo | None


class SeatRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    class_month_id: UUID | None = None   # required for monthly classes
    note: str | None = Field(default=None, max_length=500)


class MySeatRequest(SeatRequestInfo):
    id: UUID
    class_id: UUID
    class_title: str
    month_start: date | None
    student_note: str | None


class SeatRequestRow(BaseModel):
    """A request as the class's staff see it."""

    id: UUID
    status: Literal["pending", "approved", "rejected", "expired", "used", "withdrawn"]
    student_member_id: UUID
    student_name: str
    student_phone: str | None
    class_id: UUID
    class_title: str
    class_month_id: UUID | None
    month_start: date | None
    student_note: str | None
    decision_note: str | None
    created_at: datetime
    decided_at: datetime | None
    held_until: datetime | None
    seats_free: int | None               # None = no limit


class SeatDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=500)


class SeatWait(BaseModel):
    """A class the student asked to be told about."""

    class_id: UUID
    class_title: str
    created_at: datetime
    available: bool                      # a seat is open now
    needs_request: bool                  # ... but the teacher accepts new students first


class KeepIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: Literal["keep", "release"]
    keep_until: AwareDatetime | None = None
    allow_over_limit: bool = False       # keep a seat although every seat is taken

    @model_validator(mode="after")
    def _until(self) -> Self:
        if (self.action == "keep") != (self.keep_until is not None):
            raise ValueError("keep_until goes with keep, and only with it")
        return self
