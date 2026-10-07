from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.claim_windows import (
    ClaimWindowEvaluation,
    FixedClaimWindow,
    RelativeClaimWindow,
    evaluate_fixed_claim_window,
    evaluate_relative_claim_window,
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


PURCHASE = date(2026, 10, 1)


@pytest.mark.parametrize(
    "offsets,opens_on,deadline_on,positions",
    [
        (
            (0, 30),
            PURCHASE,
            date(2026, 10, 31),
            ["2026-09-30", "2026-10-01", "2026-10-15", "2026-10-31", "2026-11-01"],
        ),
        (
            (30, 60),
            date(2026, 10, 31),
            date(2026, 11, 30),
            ["2026-10-30", "2026-10-31", "2026-11-15", "2026-11-30", "2026-12-01"],
        ),
    ],
)
def test_relative_inclusive_boundaries(offsets, opens_on, deadline_on, positions):
    window = RelativeClaimWindow(*offsets)
    for position, status in zip(
        positions, [S.NOT_YET_OPEN, S.OPEN, S.OPEN, S.OPEN, S.EXPIRED], strict=True
    ):
        as_of = date.fromisoformat(position)
        result = evaluate_relative_claim_window(window, PURCHASE, as_of)
        assert type(result) is ClaimWindowEvaluation
        assert type(result.status) is S
        assert result == ClaimWindowEvaluation(status, opens_on, deadline_on)
        assert result == evaluate_relative_claim_window(replace(window), PURCHASE, as_of)


@pytest.mark.parametrize("offset,claim_date", [(0, PURCHASE), (30, date(2026, 10, 31))])
@pytest.mark.parametrize("delta,status", [(-1, S.NOT_YET_OPEN), (0, S.OPEN), (1, S.EXPIRED)])
def test_relative_single_day(offset, claim_date, delta, status):
    assert evaluate_relative_claim_window(
        RelativeClaimWindow(offset, offset), PURCHASE, claim_date + timedelta(days=delta)
    ) == ClaimWindowEvaluation(status, claim_date, claim_date)


@pytest.mark.parametrize(
    "purchase,offsets,opens_on,deadline_on",
    [
        (date(2026, 1, 31), (0, 30), date(2026, 1, 31), date(2026, 3, 2)),
        (date(2026, 12, 31), (1, 30), date(2027, 1, 1), date(2027, 1, 30)),
        (date(2028, 2, 1), (28, 29), date(2028, 2, 29), date(2028, 3, 1)),
        (date.min, (0, 0), date.min, date.min),
        (date.max, (0, 0), date.max, date.max),
    ],
)
def test_relative_calendar_arithmetic(purchase, offsets, opens_on, deadline_on):
    assert evaluate_relative_claim_window(
        RelativeClaimWindow(*offsets), purchase, deadline_on
    ) == ClaimWindowEvaluation(S.OPEN, opens_on, deadline_on)


@pytest.mark.parametrize("field", ["start_offset_days", "end_offset_days"])
@pytest.mark.parametrize("invalid", ["30", 30.0, Decimal("30"), None, True, False, object()])
def test_relative_offset_types(field, invalid):
    with pytest.raises(TypeError, match="Claim offset must be an integer"):
        replace(RelativeClaimWindow(0, 30), **{field: invalid})


@pytest.mark.parametrize("offsets", [(-1, 30), (0, -1), (60, 30)])
def test_relative_invalid_offset_values(offsets):
    with pytest.raises(ValueError):
        RelativeClaimWindow(*offsets)


@pytest.mark.parametrize("field", ["purchase_date", "evaluation_date"])
@pytest.mark.parametrize("invalid", [*INVALID_DATES, datetime(2026, 10, 1, tzinfo=UTC), True])
def test_relative_dates_are_not_coerced(field, invalid):
    arguments = dict(purchase_date=PURCHASE, evaluation_date=PURCHASE)
    with pytest.raises(TypeError):
        evaluate_relative_claim_window(RelativeClaimWindow(0, 30), **(arguments | {field: invalid}))


@pytest.mark.parametrize("invalid", [None, WINDOW, (0, 30), object(), PromotionStatus.EXPIRED])
def test_relative_requires_typed_window(invalid):
    with pytest.raises(TypeError, match="Window must be a RelativeClaimWindow"):
        evaluate_relative_claim_window(invalid, PURCHASE, PURCHASE)


@pytest.mark.parametrize("offsets", [(0, 1), (1, 1), (0, 2147483647), (0, 10**100)])
def test_relative_calendar_overflow(offsets):
    with pytest.raises(
        ValueError, match="Relative claim dates exceed the supported calendar range"
    ):
        evaluate_relative_claim_window(RelativeClaimWindow(*offsets), date.max, date.max)


def test_relative_value_contract():
    window = RelativeClaimWindow(30, 60)
    assert [field.name for field in fields(window)] == ["start_offset_days", "end_offset_days"]
    assert window == replace(window)
    assert not hasattr(window, "__dict__")
    for field in fields(window):
        with pytest.raises(FrozenInstanceError):
            setattr(window, field.name, 0)
