"""A class's seat settings (docs/SEATS.md): checked by the catalogue, which owns the class form. Kept apart from
service.py, which builds on the catalogue."""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from app.core.config import get_settings
from app.core.errors import ApiError

DEFAULTS: dict[str, object] = {"seat_limit": None, "show_seat_count": True, "registration": "open",
                               "starts_on": None, "registration_after_start": None, "renewal_day": 7}

COLOMBO = ZoneInfo("Asia/Colombo")
# However late a month opens, returning students have this long to renew.
MIN_RENEWAL = timedelta(days=3)


def renew_until(month_start: date, renewal_day: int, opened_at: datetime) -> datetime:
    """Until when returning students' seats are kept in a month that opened at `opened_at`: the end of the renewal
    day, Sri Lanka time, and at least MIN_RENEWAL. Fixed when the month opens; staff can move it."""
    end_of_day = datetime(month_start.year, month_start.month, renewal_day, tzinfo=COLOMBO) + timedelta(days=1)
    return max(end_of_day.astimezone(UTC), opened_at + MIN_RENEWAL)


def check(values: dict[str, Any], changed: set[str]) -> None:
    """`values` are all the settings after the change, `changed` the ones it touches. Until the screens exist
    (SEATS_ENABLED) a setting can only go back to its default, so no class is limited where students can't see it."""
    if values["registration_after_start"] is not None and values["starts_on"] is None:
        raise ApiError("SEATS_INVALID", "Choose the start date first.", status_code=422)
    if not get_settings().seats_enabled and any(values[k] != DEFAULTS[k] for k in changed):
        raise ApiError("SEATS_NOT_AVAILABLE", "Seat limits aren't available yet.", status_code=409)
