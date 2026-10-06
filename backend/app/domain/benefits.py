"""Benefit classification and display text, independent of reward calculation."""

from dataclasses import dataclass
from enum import StrEnum


class BenefitType(StrEnum):
    CASHBACK = "cashback"
    EXTENDED_WARRANTY = "extended_warranty"
    FREE_GIFT = "free_gift"


@dataclass(frozen=True, slots=True)
class Benefit:
    """Common benefit value; display text must never be parsed into reward rules."""

    benefit_type: BenefitType
    name: str
    description: str | None = None

    def __post_init__(self) -> None:
        # Validate at construction too: annotations alone cannot reject unknown data.
        object.__setattr__(self, "benefit_type", BenefitType(self.benefit_type))
        if not isinstance(self.name, str):
            raise TypeError("Benefit name must be a string")
        if self.description is not None and not isinstance(self.description, str):
            raise TypeError("Benefit description must be a string or None")
