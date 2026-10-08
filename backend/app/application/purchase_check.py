"""Transport-independent input for the future purchase-check use case."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.application.identity_matching import IdentityResolver
    from app.application.promotion_candidate_matching import UnresolvedPurchaseIdentity
    from app.application.purchase_check_details import CheckPurchaseRepository, CheckPurchaseResult

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


def check_purchase(
    request: CheckPurchaseRequest,
    *,
    evaluation_date: date,
    identity_resolver: "IdentityResolver",
    promotion_repository: "CheckPurchaseRepository",
) -> "CheckPurchaseResult | UnresolvedPurchaseIdentity":
    """Check one purchase against an injected, coherent published read snapshot."""
    # Imports are local because candidate matching owns the existing input dependency.
    from datetime import datetime

    import structlog

    from app.application.identity_matching import IdentityPersistenceError
    from app.application.promotion_candidate_matching import (
        UnresolvedPurchaseIdentity,
        match_promotion_candidates,
    )
    from app.application.promotions import PromotionPersistenceError
    from app.application.purchase_check_details import (
        CheckPurchaseResult,
        NoMatchReason,
        PublishedPromotionDataError,
        PublishedPromotionDetails,
    )

    logger = structlog.get_logger(__name__)
    if not isinstance(request, CheckPurchaseRequest):
        logger.warning("check_purchase_failed", category="validation")
        raise TypeError("Request must be CheckPurchaseRequest")
    if not isinstance(evaluation_date, date) or isinstance(evaluation_date, datetime):
        logger.warning("check_purchase_failed", category="validation")
        raise TypeError("Evaluation date must be a calendar date")
    try:
        matched = match_promotion_candidates(request, identity_resolver, promotion_repository)
        if isinstance(matched, UnresolvedPurchaseIdentity):
            return matched
        if not matched.candidates:
            return CheckPurchaseResult(
                evaluation_date,
                matched.identity,
                (),
                NoMatchReason.NO_MATCHING_PUBLISHED_PROMOTIONS,
                ("No matching published promotion was found for this purchase.",),
            )
        ids = tuple(candidate.promotion_variant_id for candidate in matched.candidates)
        details = promotion_repository.load_check_purchase_candidates(ids)
        if not isinstance(details, tuple) or any(
            not isinstance(detail, PublishedPromotionDetails) for detail in details
        ):
            raise PublishedPromotionDataError("Invalid published candidate projection")
        by_id = {detail.promotion_variant_id: detail for detail in details}
        if len(set(ids)) != len(ids) or len(by_id) != len(details) or set(by_id) != set(ids):
            raise PublishedPromotionDataError("Published candidate details are inconsistent")
        results = tuple(
            _evaluate_candidate(request, evaluation_date, matched.identity, candidate, by_id[key])
            for candidate, key in zip(matched.candidates, ids, strict=True)
        )
        counts = {}
        for result in results:
            key = result.eligibility.classification.value
            counts[key] = counts.get(key, 0) + 1
        logger.info(
            "check_purchase_completed",
            candidate_count=len(ids),
            result_count=len(results),
            classification_counts=counts,
            missing_claim_window_count=sum(result.claim_window is None for result in results),
            missing_reward_amount_count=sum(
                benefit.reward_unavailable_reason is not None
                for result in results
                for benefit in result.benefits
            ),
        )
        return CheckPurchaseResult(evaluation_date, matched.identity, results)
    except (IdentityPersistenceError, PromotionPersistenceError):
        logger.error("check_purchase_failed", category="persistence")
        raise
    except (ValueError, TypeError) as error:
        logger.error("check_purchase_failed", category="data_integrity")
        if isinstance(error, PublishedPromotionDataError):
            raise
        raise PublishedPromotionDataError("Invalid published promotion data") from None


def _evaluate_candidate(request, evaluation_date, identity, candidate, detail):
    from app.application.purchase_check_details import (
        CheckPurchaseBenefit,
        CheckPurchasePromotionResult,
        PublishedPromotionDataError,
        RewardUnavailableReason,
    )
    from app.domain.benefits import BenefitType
    from app.domain.claim_windows import (
        FixedClaimWindow,
        RelativeClaimWindow,
        evaluate_fixed_claim_window,
        evaluate_relative_claim_window,
    )
    from app.domain.eligibility_result import classify_eligibility
    from app.domain.eligibility_rules import (
        ManufacturerRule,
        ProductRule,
        PromotionEligibilityRules,
        PurchaseDateRule,
        PurchaseEligibilityFacts,
        RetailerRule,
        evaluate_eligibility_rules,
    )
    from app.domain.promotion_lifecycle import PromotionStatus
    from app.domain.promotion_provenance import validate_publication_provenance
    from app.domain.rewards import MissingPurchasePrice, calculate_reward

    if (
        detail.promotion_id != candidate.promotion_id
        or detail.promotion_status != candidate.promotion_status
        or detail.promotion_status not in (PromotionStatus.ACTIVE, PromotionStatus.EXPIRED)
        or detail.retailer_id != candidate.retailer_id
        or detail.purchase_start_date != candidate.purchase_start_date
        or detail.purchase_end_date != candidate.purchase_end_date
        or detail.manufacturer_id != identity.manufacturer_id
        or identity.product_id not in detail.product_ids
        or (detail.retailer_id is not None and detail.retailer_id != identity.retailer_id)
        or not detail.benefits
    ):
        raise PublishedPromotionDataError("Published candidate details are inconsistent")
    facts = PurchaseEligibilityFacts(
        identity.manufacturer_id,
        identity.product_id,
        identity.retailer_id,
        request.purchase_date,
        request.purchase_price,
    )
    rules = PromotionEligibilityRules(
        manufacturer=ManufacturerRule(frozenset({detail.manufacturer_id})),
        product=ProductRule(detail.product_ids),
        retailer=RetailerRule(frozenset({detail.retailer_id}))
        if detail.retailer_id is not None
        else None,
        purchase_date=PurchaseDateRule(detail.purchase_start_date, detail.purchase_end_date)
        if detail.purchase_start_date is not None or detail.purchase_end_date is not None
        else None,
    )
    fixed = (detail.claim_start_date, detail.claim_end_date)
    relative = (detail.claim_start_offset_days, detail.claim_end_offset_days)
    has_fixed = any(value is not None for value in fixed)
    has_relative = any(value is not None for value in relative)
    if (
        (has_fixed and has_relative)
        or (has_fixed and None in fixed)
        or (has_relative and None in relative)
    ):
        raise PublishedPromotionDataError("Invalid published claim window")
    window = None
    if has_fixed:
        window = evaluate_fixed_claim_window(FixedClaimWindow(*fixed), evaluation_date)
    elif has_relative:
        window = evaluate_relative_claim_window(
            RelativeClaimWindow(*relative), request.purchase_date, evaluation_date
        )
    eligibility = classify_eligibility(
        evaluate_eligibility_rules(facts, rules), window.status if window else None
    )
    benefits = []
    for entry in sorted(detail.benefits, key=lambda value: value.benefit_id):
        amount, unavailable = None, None
        if entry.benefit.benefit_type != BenefitType.CASHBACK:
            if entry.reward is not None:
                raise PublishedPromotionDataError("Non-cash benefit has a monetary reward")
        elif entry.reward is None:
            unavailable = RewardUnavailableReason.NOT_CONFIGURED
        else:
            try:
                amount = calculate_reward(
                    entry.reward,
                    purchase_price=request.purchase_price,
                    product_id=identity.product_id,
                )
            except MissingPurchasePrice:
                unavailable = RewardUnavailableReason.PURCHASE_PRICE_REQUIRED
        benefits.append(CheckPurchaseBenefit(entry.benefit_id, entry.benefit, amount, unavailable))
    sources = tuple(sorted(detail.sources, key=lambda value: (value.role.value, value.source_id)))
    return CheckPurchasePromotionResult(
        detail.promotion_id,
        detail.promotion_variant_id,
        detail.promotion_name,
        detail.variant_name,
        detail.promotion_status,
        eligibility,
        window,
        tuple(benefits),
        tuple(
            value.requirement
            for value in sorted(detail.requirements, key=lambda value: value.requirement_id)
        ),
        validate_publication_provenance(sources),
        sources,
        _explanations(eligibility, window),
    )


def _explanations(eligibility, window):
    """Ordered display items derive from the decisive machine-readable reasons."""
    from app.domain.eligibility_result import EligibilityReasonCode

    opening_text = f"Claiming opens on {window.opens_on.isoformat()}." if window else ""
    copy = {
        EligibilityReasonCode.ALL_CONFIGURED_RULES_SATISFIED: (
            "The recorded eligibility rules match this purchase."
        ),
        EligibilityReasonCode.CLAIM_WINDOW_OPEN: "The claim window is open.",
        EligibilityReasonCode.CLAIM_WINDOW_EXPIRED: "The claim deadline has passed.",
        EligibilityReasonCode.CLAIM_WINDOW_UNSPECIFIED: "The claim period is not available.",
        EligibilityReasonCode.CLAIM_WINDOW_NOT_YET_OPEN: opening_text,
    }
    return tuple(
        copy[reason.code]
        if reason.code in copy
        else f"Recorded rule outcome: {reason.code.value.replace('_', ' ')}."
        for reason in eligibility.reasons
    )
