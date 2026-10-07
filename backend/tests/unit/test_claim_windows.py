from dataclasses import FrozenInstanceError, fields, replace
from datetime import date, datetime

import pytest

from app.domain.claim_windows import (
    ClaimWindowEvaluation,
    FixedClaimWindow,
    evaluate_fixed_claim_window,
)
from app.domain.eligibility_result import ClaimWindowStatus as S
from app.domain.promotion_lifecycle import PromotionStatus

START, END = date(2026, 11, 1), date(2026, 11, 30)
WINDOW = FixedClaimWindow(START, END)
INVALID_DATES = ["2026-11-01", datetime(2026, 11, 1), None, object(), 1]


@pytest.mark.parametrize(
    "as_of,status",
    [
        (date(2026, 10, 31), S.NOT_YET_OPEN),
        (START, S.OPEN),
        (date(2026, 11, 15), S.OPEN),
        (END, S.OPEN),
        (date(2026, 12, 1), S.EXPIRED),
    ],
)
def test_inclusive_window_and_retained_dates(as_of, status):
    result = evaluate_fixed_claim_window(WINDOW, as_of)
    assert result == ClaimWindowEvaluation(status, START, END)
    assert result.status is status
    assert type(result.status) is S
    assert result == evaluate_fixed_claim_window(replace(WINDOW), as_of)


@pytest.mark.parametrize(
    "as_of,status",
    [(date(2026, 11, 29), S.NOT_YET_OPEN), (END, S.OPEN), (date(2026, 12, 1), S.EXPIRED)],
)
def test_one_day_window(as_of, status):
    assert evaluate_fixed_claim_window(FixedClaimWindow(END, END), as_of) == (
        ClaimWindowEvaluation(status, END, END)
    )


@pytest.mark.parametrize("field", ["start_date", "end_date"])
@pytest.mark.parametrize("invalid", INVALID_DATES)
def test_invalid_window_dates(field, invalid):
    with pytest.raises(TypeError):
        replace(WINDOW, **{field: invalid})


def test_inverted_window():
    with pytest.raises(ValueError):
        FixedClaimWindow(END, START)


@pytest.mark.parametrize("invalid", INVALID_DATES)
def test_invalid_evaluation_date(invalid):
    with pytest.raises(TypeError):
        evaluate_fixed_claim_window(WINDOW, invalid)


@pytest.mark.parametrize("invalid", [None, (START, END), object(), PromotionStatus.EXPIRED])
def test_missing_or_untyped_window_cannot_produce_status(invalid):
    with pytest.raises(TypeError):
        evaluate_fixed_claim_window(invalid, START)


@pytest.mark.parametrize("value", [WINDOW, evaluate_fixed_claim_window(WINDOW, START)])
def test_values_are_immutable(value):
    for field in fields(value):
        with pytest.raises(FrozenInstanceError):
            setattr(value, field.name, None)
    assert not hasattr(value, "__dict__")


@pytest.mark.parametrize("status", ["open", "expired", None, *list(PromotionStatus)])
def test_result_rejects_noncanonical_status_and_lifecycle(status):
    with pytest.raises(TypeError):
        ClaimWindowEvaluation(status, START, END)


@pytest.mark.parametrize("field", ["opens_on", "deadline_on"])
@pytest.mark.parametrize("invalid", INVALID_DATES)
def test_result_validates_dates(field, invalid):
    with pytest.raises(TypeError):
        replace(ClaimWindowEvaluation(S.OPEN, START, END), **{field: invalid})


def test_result_rejects_inverted_bounds():
    with pytest.raises(ValueError):
        ClaimWindowEvaluation(S.OPEN, END, START)
