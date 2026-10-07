"""Transport-independent input for the future purchase-check use case."""

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from app.domain.identity_normalisation import normalise_identifier, normalise_text


@dataclass(frozen=True, slots=True)
class CheckPurchaseRequest:
    """Validated raw purchase input; construction performs no identity resolution."""

    brand: str
    model: str
    retailer: str
    purchase_date: date
    purchase_price: Decimal | None = None

    def __post_init__(self) -> None:
        # Reuse identity validation without replacing the caller's raw strings.
        normalise_text(self.brand)
        normalise_identifier(self.model)
        normalise_text(self.retailer)
        if not isinstance(self.purchase_date, date) or isinstance(self.purchase_date, datetime):
            raise TypeError("Purchase date must be a calendar date, not a datetime")
        if self.purchase_price is None:
            return
        if not isinstance(self.purchase_price, Decimal):
            raise TypeError("Purchase price must be a Decimal or None")
        if not self.purchase_price.is_finite() or self.purchase_price < 0:
            raise ValueError("Purchase price must be finite and non-negative")
        if self.purchase_price.as_tuple().exponent < -2:
            raise ValueError("Purchase price must have at most two fractional decimal places")
