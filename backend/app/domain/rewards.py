"""Typed GBP reward definitions and pure calculation, separate from eligibility."""

from dataclasses import dataclass
from decimal import MAX_EMAX, MIN_EMIN, ROUND_HALF_UP, Context, Decimal, localcontext
from enum import StrEnum
from typing import ClassVar
from uuid import UUID

from app.domain.purchase_values import validate_purchase_price


class RewardType(StrEnum):
    FIXED_AMOUNT = "fixed_amount"
    PERCENTAGE = "percentage"
    PRODUCT_SPECIFIC = "product_specific"


class MissingPurchasePrice(ValueError):
    """Percentage calculation requires a known qualifying price."""


class MissingProductReward(ValueError):
    """The definition has no configured value for this canonical product."""


def _validate_value(value: Decimal, *, places: int, label: str) -> None:
    if not isinstance(value, Decimal):
        raise TypeError(f"{label} must be a Decimal")
    if not value.is_finite() or value <= 0:
        raise ValueError(f"{label} must be finite and strictly positive")
    if value.as_tuple().exponent < -places:
        raise ValueError(f"{label} must have at most {places} fractional decimal places")


@dataclass(frozen=True, slots=True)
class FixedAmountReward:
    amount: Decimal
    reward_type: ClassVar[RewardType] = RewardType.FIXED_AMOUNT

    def __post_init__(self) -> None:
        _validate_value(self.amount, places=2, label="Reward amount")


@dataclass(frozen=True, slots=True)
class PercentageReward:
    percentage: Decimal
    reward_type: ClassVar[RewardType] = RewardType.PERCENTAGE

    def __post_init__(self) -> None:
        _validate_value(self.percentage, places=4, label="Reward percentage")
        if self.percentage > 100:
            raise ValueError("Reward percentage must not exceed 100")


@dataclass(frozen=True, slots=True)
class ProductRewardValue:
    product_id: UUID
    amount: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.product_id, UUID):
            raise TypeError("Reward product ID must be a canonical UUID")
        _validate_value(self.amount, places=2, label="Reward amount")


@dataclass(frozen=True, slots=True)
class ProductSpecificReward:
    values: tuple[ProductRewardValue, ...]
    reward_type: ClassVar[RewardType] = RewardType.PRODUCT_SPECIFIC

    def __post_init__(self) -> None:
        if not isinstance(self.values, (tuple, list)):
            raise TypeError("Product reward values must be a tuple or list")
        values = tuple(self.values)
        if not values:
            raise ValueError("Product-specific rewards must contain at least one value")
        if any(not isinstance(value, ProductRewardValue) for value in values):
            raise TypeError("Product reward entries must be ProductRewardValue values")
        if len({value.product_id for value in values}) != len(values):
            raise ValueError("Product-specific reward IDs must be unique")
        object.__setattr__(
            self, "values", tuple(sorted(values, key=lambda value: value.product_id))
        )


RewardDefinition = FixedAmountReward | PercentageReward | ProductSpecificReward


def calculate_reward(
    reward: RewardDefinition,
    *,
    purchase_price: Decimal | None = None,
    product_id: UUID | None = None,
) -> Decimal:
    """Return exact GBP; only percentage results are rounded, to pence half-up."""
    if isinstance(reward, FixedAmountReward):
        return reward.amount
    if isinstance(reward, PercentageReward):
        validate_purchase_price(purchase_price)
        if purchase_price is None:
            raise MissingPurchasePrice("Percentage reward requires a purchase price")
        # Enough precision for the exact product and the final pence coefficient.
        # A fresh context also isolates traps and exponent limits from the caller.
        precision = max(
            len(purchase_price.as_tuple().digits) + len(reward.percentage.as_tuple().digits),
            purchase_price.adjusted() + 4,
            8,
        )
        context = Context(prec=precision, rounding=ROUND_HALF_UP, Emax=MAX_EMAX, Emin=MIN_EMIN)
        with localcontext(context):
            return (purchase_price * reward.percentage / Decimal(100)).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
    if isinstance(reward, ProductSpecificReward):
        if not isinstance(product_id, UUID):
            raise TypeError("Product-specific calculation requires a canonical product UUID")
        for value in reward.values:
            if value.product_id == product_id:
                return value.amount
        raise MissingProductReward("No reward configured for this canonical product")
    raise TypeError("Reward must be a supported typed reward definition")
