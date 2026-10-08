from dataclasses import FrozenInstanceError, replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from app.application.promotion_candidate_matching import (
    PromotionCandidate,
    UnresolvedPurchaseIdentity,
)
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.application.purchase_check_details import (
    NoMatchReason,
    PublishedBenefit,
    PublishedPromotionDataError,
    PublishedPromotionDetails,
    PublishedRequirement,
    RewardUnavailableReason,
)
from app.domain.benefits import Benefit, BenefitType
from app.domain.eligibility_result import EligibilityClassification as Classification
from app.domain.identity_normalisation import MatchResult, MatchStatus
from app.domain.promotion_lifecycle import PromotionStatus
from app.domain.promotion_provenance import PromotionSourceRecord
from app.domain.requirements import Requirement, RequirementType
from app.domain.rewards import (
    FixedAmountReward,
    PercentageReward,
    ProductRewardValue,
    ProductSpecificReward,
)

MAKER, SHOP, PRODUCT, PROMO, VARIANT = (UUID(int=i) for i in range(1, 6))
DAY = date(2024, 2, 29)
STAMP = datetime(2024, 1, 1, tzinfo=UTC)
REQUEST = CheckPurchaseRequest("Maker", "Model", "Shop", DAY, Decimal("199.99"))
SOURCES = tuple(
    PromotionSourceRecord(
        UUID(int=i), role, f"https://example.com/{role}", "web_page", STAMP, STAMP
    )
    for i, role in ((10, "primary"), (11, "claim"), (12, "supporting"))
)
DETAIL = PublishedPromotionDetails(
    PROMO,
    VARIANT,
    "Offer",
    "Variant",
    PromotionStatus.ACTIVE,
    MAKER,
    SHOP,
    frozenset({PRODUCT}),
    DAY,
    DAY,
    DAY,
    date(2024, 3, 30),
    benefits=(
        PublishedBenefit(
            UUID(int=20), Benefit("cashback", "Reward"), FixedAmountReward(Decimal("100"))
        ),
    ),
    requirements=(
        PublishedRequirement(UUID(int=31), Requirement("receipt", "original")),
        PublishedRequirement(UUID(int=30), Requirement("installation_evidence", "install")),
        PublishedRequirement(UUID(int=32), Requirement("receipt", "duplicate kind")),
    ),
    sources=tuple(reversed(SOURCES)),
)


class Resolver:
    field = None
    candidate_ids = ()

    def resolve_manufacturer(self, value):
        return MatchResult(self.candidate_ids if self.field == "brand" else (MAKER,))

    def resolve_retailer(self, value):
        return MatchResult(self.candidate_ids if self.field == "retailer" else (SHOP,))

    def resolve_product(self, value, **kwargs):
        return MatchResult(self.candidate_ids if self.field == "model" else (PRODUCT,))


class Repository:
    def __init__(self, details=(DETAIL,), candidates=None):
        self.details = details
        self.loaded = False
        self.candidates = (
            candidates
            if candidates is not None
            else tuple(
                PromotionCandidate(
                    d.promotion_id,
                    d.promotion_variant_id,
                    d.promotion_status,
                    d.retailer_id,
                    d.purchase_start_date,
                    d.purchase_end_date,
                )
                for d in details
            )
        )

    def find_promotion_candidates(self, **kwargs):
        return self.candidates

    def load_check_purchase_candidates(self, ids):
        self.loaded = True
        return self.details


def run(detail=DETAIL, *, request=REQUEST, evaluation_date=DAY, repository=None, resolver=None):
    return check_purchase(
        request,
        evaluation_date=evaluation_date,
        identity_resolver=resolver or Resolver(),
        promotion_repository=repository or Repository((detail,)),
    )


def test_complete_result_immutable_detached_and_deterministic():
    result = run()
    assert run() == result
    offer = result.promotions[0]
    assert offer.eligibility.classification == Classification.ELIGIBLE
    assert offer.benefits[0].cashback_reward_gbp == Decimal("100")
    assert tuple(r.requirement_type for r in offer.requirements) == (
        RequirementType.INSTALLATION_EVIDENCE,
        RequirementType.RECEIPT,
        RequirementType.RECEIPT,
    )
    assert offer.sources == tuple(
        sorted(SOURCES, key=lambda value: (value.role.value, value.source_id))
    )
    assert offer.provenance.claim_url == "https://example.com/claim"
    assert len(offer.eligibility.rule_evaluations) == 4
    assert "match this purchase" in offer.explanation[0]
    with pytest.raises(FrozenInstanceError):
        result.evaluation_date = DAY


@pytest.mark.parametrize("status", [PromotionStatus.ACTIVE, PromotionStatus.EXPIRED])
@pytest.mark.parametrize(
    "evaluation,expected",
    [
        (date(2024, 2, 28), Classification.CLAIM_NOT_YET_OPEN),
        (DAY, Classification.ELIGIBLE),
        (date(2024, 3, 30), Classification.ELIGIBLE),
        (date(2024, 3, 31), Classification.EXPIRED),
    ],
)
def test_fixed_window_independent_of_lifecycle(status, evaluation, expected):
    assert (
        run(replace(DETAIL, promotion_status=status), evaluation_date=evaluation)
        .promotions[0]
        .eligibility.classification
        == expected
    )


@pytest.mark.parametrize(
    "purchase,start,end,opens,deadline",
    [
        (DAY, 0, 30, DAY, date(2024, 3, 30)),
        (DAY, 30, 60, date(2024, 3, 30), date(2024, 4, 29)),
        (date(2023, 12, 31), 0, 30, date(2023, 12, 31), date(2024, 1, 30)),
    ],
)
def test_relative_dates(purchase, start, end, opens, deadline):
    detail = replace(
        DETAIL,
        purchase_start_date=None,
        purchase_end_date=None,
        claim_start_date=None,
        claim_end_date=None,
        claim_start_offset_days=start,
        claim_end_offset_days=end,
    )
    result = run(detail, request=replace(REQUEST, purchase_date=purchase), evaluation_date=opens)
    assert result.promotions[0].claim_window.opens_on == opens
    assert result.promotions[0].claim_window.deadline_on == deadline
    assert result.promotions[0].eligibility.classification == Classification.ELIGIBLE


def test_absent_window_is_uncertain():
    result = run(replace(DETAIL, claim_start_date=None, claim_end_date=None)).promotions[0]
    assert result.claim_window is None
    assert result.eligibility.classification == Classification.POTENTIALLY_ELIGIBLE
    assert result.eligibility.reasons[-1].code == "claim_window_unspecified"


@pytest.mark.parametrize("field", ["brand", "retailer", "model"])
@pytest.mark.parametrize(
    "ids,status", [((), MatchStatus.NOT_FOUND), ((MAKER, SHOP), MatchStatus.AMBIGUOUS)]
)
def test_unresolved_identity_preserved_without_details(field, ids, status):
    resolver, repository = Resolver(), Repository()
    resolver.field, resolver.candidate_ids = field, ids
    assert run(resolver=resolver, repository=repository) == UnresolvedPurchaseIdentity(
        field, status, ids
    )
    assert not repository.loaded


def test_resolved_no_match_distinct():
    repository = Repository(())
    result = run(repository=repository)
    assert result.promotions == ()
    assert result.no_match_reason == NoMatchReason.NO_MATCHING_PUBLISHED_PROMOTIONS
    assert not repository.loaded


def test_hydration_order_preserves_each_variant():
    second = replace(DETAIL, promotion_variant_id=UUID(int=6), retailer_id=None)
    third = replace(DETAIL, promotion_id=UUID(int=7), promotion_variant_id=UUID(int=8))
    repository = Repository((DETAIL, second, third))
    repository.details = (third, second, DETAIL)
    assert tuple(value.promotion_variant_id for value in run(repository=repository).promotions) == (
        VARIANT,
        UUID(int=6),
        UUID(int=8),
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"promotion_status": PromotionStatus.ARCHIVED},
        {"promotion_status": PromotionStatus.REVIEW},
        {"promotion_id": UUID(int=90)},
        {"manufacturer_id": UUID(int=90)},
        {"product_ids": frozenset({UUID(int=90)})},
        {"retailer_id": UUID(int=90)},
        {"benefits": ()},
        {"claim_end_date": None},
        {"claim_start_offset_days": 0, "claim_end_offset_days": 30},
        {"claim_start_date": date(2025, 1, 1)},
    ],
)
def test_invalid_details_fail_whole_check(changes):
    repository = Repository()
    repository.details = (replace(DETAIL, **changes),)
    with pytest.raises(PublishedPromotionDataError):
        run(repository=repository)


@pytest.mark.parametrize(
    "details", [(), (DETAIL, DETAIL), (replace(DETAIL, promotion_variant_id=UUID(int=90)),)]
)
def test_detail_missing_duplicate_extra_fail(details):
    repository = Repository()
    repository.details = details
    with pytest.raises(PublishedPromotionDataError):
        run(repository=repository)


@pytest.mark.parametrize(
    "reward,price,amount,reason",
    [
        (FixedAmountReward(Decimal("100")), None, Decimal("100"), None),
        (PercentageReward(Decimal("10")), Decimal("199.99"), Decimal("20.00"), None),
        (
            PercentageReward(Decimal("10")),
            None,
            None,
            RewardUnavailableReason.PURCHASE_PRICE_REQUIRED,
        ),
        (
            ProductSpecificReward((ProductRewardValue(PRODUCT, Decimal("42")),)),
            None,
            Decimal("42"),
            None,
        ),
        (None, None, None, RewardUnavailableReason.NOT_CONFIGURED),
    ],
)
def test_cashback_reward_independent_of_eligibility(reward, price, amount, reason):
    detail = replace(DETAIL, benefits=(replace(DETAIL.benefits[0], reward=reward),))
    result = run(detail, request=replace(REQUEST, purchase_price=price)).promotions[0]
    assert result.eligibility.classification == Classification.ELIGIBLE
    assert result.benefits[0].cashback_reward_gbp == amount
    assert result.benefits[0].reward_unavailable_reason == reason


@pytest.mark.parametrize("kind", [BenefitType.EXTENDED_WARRANTY, BenefitType.FREE_GIFT])
def test_non_cash_preserved_without_value(kind):
    entry = PublishedBenefit(UUID(int=21), Benefit(kind, "Gift"))
    result = run(replace(DETAIL, benefits=DETAIL.benefits + (entry,))).promotions[0]
    assert result.benefits[1].benefit.benefit_type == kind
    assert result.benefits[1].cashback_reward_gbp is None
    with pytest.raises(PublishedPromotionDataError):
        run(replace(DETAIL, benefits=(replace(entry, reward=FixedAmountReward(Decimal("1"))),)))


def test_missing_product_specific_mapping_is_data_error():
    reward = ProductSpecificReward((ProductRewardValue(SHOP, Decimal("1")),))
    with pytest.raises(PublishedPromotionDataError):
        run(replace(DETAIL, benefits=(replace(DETAIL.benefits[0], reward=reward),)))


@pytest.mark.parametrize(
    "sources",
    [
        (),
        (SOURCES[0],),
        (SOURCES[0], SOURCES[0], SOURCES[1]),
        (replace(SOURCES[0], verified_at=None), SOURCES[1]),
        (SOURCES[0], replace(SOURCES[1], verified_at=None)),
    ],
)
def test_invalid_provenance_rejected(sources):
    with pytest.raises(PublishedPromotionDataError):
        run(replace(DETAIL, sources=sources))


@pytest.mark.parametrize("value", [None, "2024-02-29", datetime(2024, 2, 29)])
def test_bad_evaluation_before_any_work(value):
    with pytest.raises(TypeError):
        run(evaluation_date=value)


def test_bad_request_and_safe_persistence_failure():
    with pytest.raises(TypeError):
        run(request={})
    repository = Repository()

    def fail(**kwargs):
        raise PromotionPersistenceError("safe failure")

    repository.find_promotion_candidates = fail
    with pytest.raises(PromotionPersistenceError, match="safe failure"):
        run(repository=repository)


def test_relative_overflow_is_data_error():
    detail = replace(
        DETAIL,
        purchase_start_date=None,
        purchase_end_date=None,
        claim_start_date=None,
        claim_end_date=None,
        claim_start_offset_days=0,
        claim_end_offset_days=30,
    )
    with pytest.raises(PublishedPromotionDataError):
        run(detail, request=replace(REQUEST, purchase_date=date.max))


@pytest.mark.parametrize(
    "changes",
    [
        {"claim_start_date": None, "claim_end_date": None, "claim_start_offset_days": 0},
        {
            "claim_start_date": None,
            "claim_end_date": None,
            "claim_start_offset_days": -1,
            "claim_end_offset_days": 30,
        },
        {
            "claim_start_date": None,
            "claim_end_date": None,
            "claim_start_offset_days": 30,
            "claim_end_offset_days": 0,
        },
    ],
)
def test_malformed_relative_windows_fail(changes):
    with pytest.raises(PublishedPromotionDataError):
        run(replace(DETAIL, **changes))


def test_projection_requires_immutable_typed_associations():
    with pytest.raises(PublishedPromotionDataError):
        replace(DETAIL, benefits=list(DETAIL.benefits))
    with pytest.raises(PublishedPromotionDataError):
        replace(DETAIL, product_ids=set(DETAIL.product_ids))
    with pytest.raises(PublishedPromotionDataError):
        replace(DETAIL.benefits[0], reward="unsupported")
    with pytest.raises(PublishedPromotionDataError):
        replace(DETAIL, requirements=("unsupported",))
    repository = Repository()
    repository.details = ("raw ORM or payload",)
    with pytest.raises(PublishedPromotionDataError):
        run(repository=repository)
