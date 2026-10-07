"""Fixed inclusive calendar claim windows, independent of purchase and lifecycle."""

from dataclasses import dataclass
from datetime import date, datetime

from app.domain.eligibility_result import ClaimWindowStatus


def _calendar_date(value: date) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError("Claim date must be a calendar date, not a datetime")


def _bounds(start: date, end: date) -> None:
    _calendar_date(start)
    _calendar_date(end)
    if start > end:
        raise ValueError("Claim start date must not follow end date")


@dataclass(frozen=True, slots=True)
class FixedClaimWindow:
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        _bounds(self.start_date, self.end_date)


@dataclass(frozen=True, slots=True)
class ClaimWindowEvaluation:
    status: ClaimWindowStatus
    opens_on: date
    deadline_on: date

    def __post_init__(self) -> None:
        if not isinstance(self.status, ClaimWindowStatus):
            raise TypeError("Claim status must be a ClaimWindowStatus")
        _bounds(self.opens_on, self.deadline_on)


def evaluate_fixed_claim_window(
    window: FixedClaimWindow, evaluation_date: date
) -> ClaimWindowEvaluation:
    """Evaluate supplied calendar data; both opening and deadline days are open."""
    if not isinstance(window, FixedClaimWindow):
        raise TypeError("Window must be a FixedClaimWindow")
    _calendar_date(evaluation_date)
    if evaluation_date < window.start_date:
        status = ClaimWindowStatus.NOT_YET_OPEN
    elif evaluation_date > window.end_date:
        status = ClaimWindowStatus.EXPIRED
    else:
        status = ClaimWindowStatus.OPEN
    return ClaimWindowEvaluation(status, window.start_date, window.end_date)
