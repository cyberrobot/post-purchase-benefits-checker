"""Inclusive calendar claim windows, independent of promotion lifecycle."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from app.domain.eligibility_result import ClaimWindowStatus
from app.domain.purchase_values import validate_purchase_date


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
    minimum_days_after_purchase: int | None = None

    def __post_init__(self) -> None:
        _bounds(self.start_date, self.end_date)
        wait = self.minimum_days_after_purchase
        if wait is not None:
            if type(wait) is not int:
                raise TypeError("Minimum wait must be an integer")
            if not 0 <= wait <= 3652058:
                raise ValueError("Minimum wait is outside the supported calendar range")


@dataclass(frozen=True, slots=True)
class RelativeClaimWindow:
    start_offset_days: int
    end_offset_days: int

    def __post_init__(self) -> None:
        for offset in (self.start_offset_days, self.end_offset_days):
            if type(offset) is not int:
                raise TypeError("Claim offset must be an integer number of calendar days")
            if offset < 0:
                raise ValueError("Claim offset must be non-negative")
        if self.start_offset_days > self.end_offset_days:
            raise ValueError("Claim start offset must not exceed end offset")


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
    window: FixedClaimWindow, evaluation_date: date, purchase_date: date | None = None
) -> ClaimWindowEvaluation:
    """Evaluate supplied calendar data; both opening and deadline days are open."""
    if not isinstance(window, FixedClaimWindow):
        raise TypeError("Window must be a FixedClaimWindow")
    _calendar_date(evaluation_date)
    opens_on = window.start_date
    if window.minimum_days_after_purchase is not None:
        validate_purchase_date(purchase_date)
        try:
            opens_on = max(
                opens_on, purchase_date + timedelta(days=window.minimum_days_after_purchase)
            )
        except OverflowError:
            raise ValueError("Claim dates exceed the supported calendar range") from None
        _bounds(opens_on, window.end_date)
    if evaluation_date < opens_on:
        status = ClaimWindowStatus.NOT_YET_OPEN
    elif evaluation_date > window.end_date:
        status = ClaimWindowStatus.EXPIRED
    else:
        status = ClaimWindowStatus.OPEN
    return ClaimWindowEvaluation(status, opens_on, window.end_date)


def evaluate_relative_claim_window(
    window: RelativeClaimWindow, purchase_date: date, evaluation_date: date
) -> ClaimWindowEvaluation:
    """Derive inclusive bounds from purchase day; no clock or lifecycle input."""
    if not isinstance(window, RelativeClaimWindow):
        raise TypeError("Window must be a RelativeClaimWindow")
    validate_purchase_date(purchase_date)
    _calendar_date(evaluation_date)
    try:
        opens_on = purchase_date + timedelta(days=window.start_offset_days)
        deadline_on = purchase_date + timedelta(days=window.end_offset_days)
    except OverflowError:
        raise ValueError("Relative claim dates exceed the supported calendar range") from None
    return evaluate_fixed_claim_window(FixedClaimWindow(opens_on, deadline_on), evaluation_date)
