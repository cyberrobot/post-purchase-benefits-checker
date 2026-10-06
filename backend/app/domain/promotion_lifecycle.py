"""Deterministic promotion lifecycle rules, independent of persistence."""

from enum import StrEnum
from types import MappingProxyType


class PromotionStatus(StrEnum):
    DISCOVERED = "discovered"
    EXTRACTED = "extracted"
    REVIEW = "review"
    ACTIVE = "active"
    EXPIRED = "expired"
    ARCHIVED = "archived"


S = PromotionStatus
HISTORICAL_STATUSES = frozenset({S.EXPIRED, S.ARCHIVED})
ALLOWED_TRANSITIONS = MappingProxyType(
    {
        S.DISCOVERED: frozenset({S.EXTRACTED, S.ARCHIVED}),
        S.EXTRACTED: frozenset({S.REVIEW, S.ARCHIVED}),
        S.REVIEW: frozenset({S.EXTRACTED, S.ACTIVE, S.ARCHIVED}),
        S.ACTIVE: frozenset({S.EXPIRED, S.ARCHIVED}),
        S.EXPIRED: frozenset({S.ARCHIVED}),
        S.ARCHIVED: frozenset(),
    }
)


class InvalidPromotionTransition(ValueError):
    def __init__(self, previous: PromotionStatus, target: PromotionStatus):
        self.previous = previous
        self.target = target
        super().__init__(f"Invalid promotion transition: {previous} -> {target}")


def validate_transition(previous: PromotionStatus, target: PromotionStatus) -> bool:
    """Return whether a change is needed, or reject an unsupported transition."""
    previous, target = PromotionStatus(previous), PromotionStatus(target)
    if previous == target:
        return False
    if target not in ALLOWED_TRANSITIONS[previous]:
        raise InvalidPromotionTransition(previous, target)
    return True
