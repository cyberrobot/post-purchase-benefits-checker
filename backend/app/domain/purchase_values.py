"""Shared calendar-date and exact GBP validation; no parsing or rounding."""

from datetime import date, datetime
from decimal import Decimal


def validate_purchase_date(value: date) -> None:
    if not isinstance(value, date) or isinstance(value, datetime):
        raise TypeError("Purchase date must be a calendar date, not a datetime")


def validate_purchase_price(value: Decimal | None) -> None:
    if value is None:
        return
    if not isinstance(value, Decimal):
        raise TypeError("Purchase price must be a Decimal or None")
    if not value.is_finite() or value < 0:
        raise ValueError("Purchase price must be finite and non-negative")
    if value.as_tuple().exponent < -2:
        raise ValueError("Purchase price must have at most two fractional decimal places")
