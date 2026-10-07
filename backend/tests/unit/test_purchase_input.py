from dataclasses import FrozenInstanceError, fields
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from unittest.mock import patch

import pytest

from app.application.purchase_check import CheckPurchaseRequest

INPUT = dict(
    brand="Example Brand", model="ABC-123", retailer="Example", purchase_date=date(2026, 9, 12)
)


@pytest.mark.parametrize(
    "identities",
    [
        ("Samsung", "QE55S95D", "Currys"),
        ("Brand & Co.", "A+B-123/UK", "Retailer's Shop"),
        ("  Ｅxample Brand \t", " QE55\n S95D ", " Currys\u00a0 "),
        ("a" * 255, "b" * 255, "c" * 255),
        ("A Brand Not Yet In Reference Data", "UNKNOWN-123", "Example"),
    ],
)
def test_valid_raw_identity_input_without_resolution(identities):
    with patch(
        "app.application.identity_matching.IdentityResolver.__init__",
        side_effect=AssertionError("No resolution during construction"),
    ) as resolver:
        request = CheckPurchaseRequest(*identities, purchase_date=INPUT["purchase_date"])
    resolver.assert_not_called()
    assert (request.brand, request.model, request.retailer) == identities
    assert request.purchase_price is None


@pytest.mark.parametrize("field", ["brand", "model", "retailer"])
@pytest.mark.parametrize("value", [None, 123, True, [], b"text"])
def test_identity_types(field, value):
    with pytest.raises(TypeError, match="Identity input must be a string"):
        CheckPurchaseRequest(**(INPUT | {field: value}))


@pytest.mark.parametrize("field", ["brand", "model", "retailer"])
@pytest.mark.parametrize(
    "value", ["", " \t\n\u00a0", "a" * 256, "ß" * 255, "bad\0input", "bad\x7finput"]
)
def test_invalid_identity_values(field, value):
    with pytest.raises(ValueError, match="Identity input"):
        CheckPurchaseRequest(**(INPUT | {field: value}))


@pytest.mark.parametrize("value", [date.min, date(2024, 2, 29), date(9999, 12, 31)])
def test_calendar_date_without_time_comparison(value):
    assert CheckPurchaseRequest(**(INPUT | {"purchase_date": value})).purchase_date is value


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-12",
        datetime(2026, 9, 12),
        datetime(2026, 9, 12, tzinfo=UTC),
        None,
        1790000000,
        True,
    ],
)
def test_date_types_are_not_parsed(value):
    with pytest.raises(TypeError, match="Purchase date must be a calendar date"):
        CheckPurchaseRequest(**(INPUT | {"purchase_date": value}))


@pytest.mark.parametrize(
    "price",
    [
        None,
        Decimal("0"),
        Decimal("0.00"),
        Decimal("19.99"),
        Decimal("1299"),
        Decimal("1299.00"),
        Decimal("1E+3"),
        Decimal("-0.00"),
    ],
)
def test_valid_price_preserved_exactly(price):
    assert CheckPurchaseRequest(**INPUT, purchase_price=price).purchase_price is price


def test_missing_price_distinct_from_zero():
    missing = CheckPurchaseRequest(**INPUT)
    zero = CheckPurchaseRequest(**INPUT, purchase_price=Decimal("0"))
    assert missing.purchase_price is None
    assert zero.purchase_price == Decimal("0")
    assert missing != zero


@pytest.mark.parametrize("value", [19.99, 0.0, "19.99", "£19.99", -1, 0, True])
def test_price_types_are_not_coerced(value):
    with pytest.raises(TypeError, match="Purchase price must be a Decimal"):
        CheckPurchaseRequest(**INPUT, purchase_price=value)


@pytest.mark.parametrize(
    "value",
    [
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("19.999"),
        Decimal("19.990"),
        Decimal("0.000"),
    ],
)
def test_invalid_price_without_rounding(value):
    original = value.as_tuple()
    with pytest.raises(ValueError, match="Purchase price must"):
        CheckPurchaseRequest(**INPUT, purchase_price=value)
    assert value.as_tuple() == original


def test_price_validation_independent_of_decimal_precision():
    price = Decimal("123456789012345678901234567890.12")
    with localcontext() as context:
        context.prec = 2
        assert CheckPurchaseRequest(**INPUT, purchase_price=price).purchase_price is price
        with pytest.raises(ValueError):
            CheckPurchaseRequest(**INPUT, purchase_price=Decimal("19.999"))


@pytest.mark.parametrize("field", list(INPUT) + ["purchase_price"])
def test_immutable(field):
    with pytest.raises(FrozenInstanceError):
        setattr(CheckPurchaseRequest(**INPUT), field, None)


def test_exact_fields_and_value_equality():
    assert [field.name for field in fields(CheckPurchaseRequest)] == [
        "brand",
        "model",
        "retailer",
        "purchase_date",
        "purchase_price",
    ]
    assert CheckPurchaseRequest(**INPUT) == CheckPurchaseRequest(**INPUT)
    with pytest.raises(TypeError):
        CheckPurchaseRequest(**INPUT, currency="GBP")


@pytest.mark.parametrize("field", list(INPUT))
def test_required_fields(field):
    with pytest.raises(TypeError):
        CheckPurchaseRequest(**{key: value for key, value in INPUT.items() if key != field})
