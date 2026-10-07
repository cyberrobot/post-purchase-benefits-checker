"""Transport-independent input for the future purchase-check use case."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.identity_normalisation import normalise_identifier, normalise_text
from app.domain.purchase_values import validate_purchase_date, validate_purchase_price


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
        validate_purchase_date(self.purchase_date)
        validate_purchase_price(self.purchase_price)
