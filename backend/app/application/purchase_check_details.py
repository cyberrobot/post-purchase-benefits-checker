"""Immutable purchase-check read projection and application results."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Protocol
from uuid import UUID

from app.application.promotion_candidate_matching import (
    PromotionCandidateRepository,
    ResolvedPurchaseIdentity,
)
from app.domain.benefits import Benefit
from app.domain.claim_windows import ClaimWindowEvaluation
from app.domain.eligibility_result import EligibilityResult
from app.domain.promotion_lifecycle import PromotionStatus
from app.domain.promotion_provenance import PromotionSourceRecord, PublishedProvenance
from app.domain.requirements import Requirement
from app.domain.rewards import (
    FixedAmountReward,
    PercentageReward,
    ProductSpecificReward,
    RewardDefinition,
)


class PublishedDataErrorCode(StrEnum):
    INVALID_PROJECTION = "invalid_published_projection"
    CANDIDATE_INCONSISTENT = "published_candidate_inconsistent"
    CLAIM_WINDOW_INVALID = "published_claim_window_invalid"
    REWARD_INVALID = "published_reward_invalid"
    PROVENANCE_INVALID = "published_provenance_invalid"
    INVALID_DATA = "invalid_published_data"


class PublishedPromotionDataError(ValueError):
    """Invalid or inconsistent published content; never a negative eligibility result."""

    def __init__(self, message=None, *, code=PublishedDataErrorCode.INVALID_DATA):
        self.code = PublishedDataErrorCode(code)
        super().__init__("Invalid published promotion data")


class RewardUnavailableReason(StrEnum):
    PURCHASE_PRICE_REQUIRED = "purchase_price_required_for_reward"
    NOT_CONFIGURED = "reward_not_configured"


class NoMatchReason(StrEnum):
    NO_MATCHING_PUBLISHED_PROMOTIONS = "no_matching_published_promotions"


@dataclass(frozen=True, slots=True)
class PublishedBenefit:
    benefit_id: UUID
    benefit: Benefit
    reward: RewardDefinition | None = None

    def __post_init__(self):
        if not isinstance(self.benefit_id, UUID) or not isinstance(self.benefit, Benefit):
            raise PublishedPromotionDataError("Invalid published benefit")
        if self.reward is not None and not isinstance(
            self.reward, (FixedAmountReward, PercentageReward, ProductSpecificReward)
        ):
            raise PublishedPromotionDataError("Unsupported published reward")


@dataclass(frozen=True, slots=True)
class PublishedRequirement:
    requirement_id: UUID
    requirement: Requirement

    def __post_init__(self):
        if not isinstance(self.requirement_id, UUID) or not isinstance(
            self.requirement, Requirement
        ):
            raise PublishedPromotionDataError("Invalid published requirement")


@dataclass(frozen=True, slots=True)
class PublishedPromotionDetails:
    promotion_id: UUID
    promotion_variant_id: UUID
    promotion_name: str
    variant_name: str | None
    promotion_status: PromotionStatus
    manufacturer_id: UUID
    retailer_id: UUID | None
    product_ids: frozenset[UUID]
    purchase_start_date: date | None
    purchase_end_date: date | None
    claim_start_date: date | None = None
    claim_end_date: date | None = None
    claim_start_offset_days: int | None = None
    claim_end_offset_days: int | None = None
    benefits: tuple[PublishedBenefit, ...] = ()
    requirements: tuple[PublishedRequirement, ...] = ()
    sources: tuple[PromotionSourceRecord, ...] = ()

    def __post_init__(self):
        for value in (self.promotion_id, self.promotion_variant_id, self.manufacturer_id):
            if not isinstance(value, UUID):
                raise PublishedPromotionDataError("Invalid published identity")
        if self.retailer_id is not None and not isinstance(self.retailer_id, UUID):
            raise PublishedPromotionDataError("Invalid published retailer")
        if not isinstance(self.promotion_status, PromotionStatus):
            raise PublishedPromotionDataError("Invalid published lifecycle state")
        if not isinstance(self.promotion_name, str) or (
            self.variant_name is not None and not isinstance(self.variant_name, str)
        ):
            raise PublishedPromotionDataError("Invalid published display text")
        if not isinstance(self.product_ids, frozenset) or any(
            not isinstance(value, UUID) for value in self.product_ids
        ):
            raise PublishedPromotionDataError("Product identities must be immutable UUIDs")
        for values, kind in (
            (self.benefits, PublishedBenefit),
            (self.requirements, PublishedRequirement),
            (self.sources, PromotionSourceRecord),
        ):
            if not isinstance(values, tuple) or any(
                not isinstance(value, kind) for value in values
            ):
                raise PublishedPromotionDataError(
                    "Published associations must be immutable typed tuples"
                )
        if len({value.benefit_id for value in self.benefits}) != len(self.benefits) or (
            len({value.requirement_id for value in self.requirements}) != len(self.requirements)
        ):
            raise PublishedPromotionDataError("Duplicate published association identity")


class CheckPurchaseRepository(PromotionCandidateRepository, Protocol):
    def load_check_purchase_candidates(
        self, candidate_variant_ids: tuple[UUID, ...]
    ) -> tuple[PublishedPromotionDetails, ...]: ...


@dataclass(frozen=True, slots=True)
class CheckPurchaseBenefit:
    benefit_id: UUID
    benefit: Benefit
    cashback_reward_gbp: Decimal | None
    reward_unavailable_reason: RewardUnavailableReason | None

    @property
    def reward_unavailable_explanation(self) -> str | None:
        return {
            RewardUnavailableReason.PURCHASE_PRICE_REQUIRED: (
                "Enter the purchase price to calculate this cashback reward."
            ),
            RewardUnavailableReason.NOT_CONFIGURED: (
                "The cashback amount is not available for this promotion."
            ),
        }.get(self.reward_unavailable_reason)


@dataclass(frozen=True, slots=True)
class CheckPurchasePromotionResult:
    promotion_id: UUID
    promotion_variant_id: UUID
    promotion_name: str
    variant_name: str | None
    promotion_status: PromotionStatus
    eligibility: EligibilityResult
    claim_window: ClaimWindowEvaluation | None
    benefits: tuple[CheckPurchaseBenefit, ...]
    requirements: tuple[Requirement, ...]
    provenance: PublishedProvenance
    sources: tuple[PromotionSourceRecord, ...]
    explanation: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class CheckPurchaseResult:
    evaluation_date: date
    resolved_identity: ResolvedPurchaseIdentity
    promotions: tuple[CheckPurchasePromotionResult, ...]
    no_match_reason: NoMatchReason | None = None
    explanation: tuple[str, ...] = ()
