from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel

from app.modules.learning.schemas import OrgRef
from app.modules.seats.schemas import MySeatRequest, SeatState, SeatWait


class UpcomingLesson(BaseModel):
    """A live lesson from any of the student's classes (Today, Schedule)."""

    lesson_id: UUID
    title: str
    lesson_type: str
    scheduled_at: datetime
    duration_minutes: int | None
    class_id: UUID
    class_title: str
    unlocked: bool
    live_now: bool                       # from 15 minutes before the start until it ends
    org: OrgRef


class MonthToPay(BaseModel):
    """An open month of a joined class (or an approved past month) the student hasn't paid."""

    class_id: UUID
    class_title: str
    month_id: UUID
    month_start: date
    fee_cents: int
    currency: str
    approved_late: bool
    seat: SeatState | None               # open months: can they pay, and until when a seat is kept
    org: OrgRef


class Today(BaseModel):
    next_live: list[UpcomingLesson]
    to_pay: list[MonthToPay]
    pending_requests: int
    classes: int


class MySeatRequestRow(MySeatRequest):
    org: OrgRef


class MySeatWait(SeatWait):
    org: OrgRef


class MyRequest(BaseModel):
    id: UUID
    status: str
    student_note: str | None
    decision_note: str | None
    created_at: datetime
    month_id: UUID
    month_start: date
    class_id: UUID
    class_title: str
    org: OrgRef
