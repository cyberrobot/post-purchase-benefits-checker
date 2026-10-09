from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from app.domain.benefits import Benefit
from app.domain.claim_windows import FixedClaimWindow, RelativeClaimWindow
from app.domain.promotion_validation import (
    DraftBenefit,
    PromotionValidationSnapshot,
    ValidationBenefit,
    ValidationSource,
    ValidationVariant,
    validate_promotion_for_publication,
)
from app.domain.rewards import FixedAmountReward, ProductRewardValue, ProductSpecificReward
from tests.unit.test_promotion_provenance import sources


def valid_snapshot():
    manufacturer, product = UUID(int=1), UUID(int=2)
    return PromotionValidationSnapshot(
        manufacturer,
        "Campaign",
        "campaign",
        date(2026, 10, 1),
        None,
        RelativeClaimWindow(0, 0),
        (
            ValidationVariant(
                "all",
                None,
                None,
                (product,),
                (
                    ValidationBenefit(
                        Benefit("cashback", "Cashback"), FixedAmountReward(Decimal("50.00"))
                    ),
                ),
                product_manufacturers=((product, manufacturer),),
            ),
        ),
        tuple(ValidationSource(s.source_id, s.role, s) for s in sources()),
    )


def test_valid_and_immutable():
    snapshot = valid_snapshot()
    assert validate_promotion_for_publication(snapshot).can_publish
    assert (
        validate_promotion_for_publication(replace(snapshot, variants=snapshot.variants * 2))
        .issues[0]
        .code
        == "duplicate_variant_code"
    )
    with pytest.raises(FrozenInstanceError):
        snapshot.name = "changed"


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("manufacturer_id", None, "missing_manufacturer"),
        ("manufacturer_exists", False, "manufacturer_not_found"),
        ("claim_window", None, "missing_claim_window"),
        ("variants", (), "missing_variant"),
        ("sources", (), "missing_primary_source"),
        ("name", " ", "missing_promotion_name"),
        ("slug", "BAD", "invalid_promotion_slug"),
    ],
)
def test_incomplete(field, value, code):
    report = validate_promotion_for_publication(replace(valid_snapshot(), **{field: value}))
    assert not report.can_publish
    assert code in {i.code for i in report.issues}


@pytest.mark.parametrize(
    "change,code",
    [
        ({"product_ids": ()}, "missing_product"),
        ({"benefits": ()}, "missing_benefit"),
        ({"product_manufacturers": ((UUID(int=2), UUID(int=9)),)}, "product_manufacturer_mismatch"),
        ({"retailer_id": UUID(int=3), "retailer_exists": False}, "retailer_not_found"),
        (
            {"benefits": (ValidationBenefit(Benefit("cashback", "Cashback")),)},
            "missing_cashback_reward",
        ),
        (
            {
                "benefits": (
                    ValidationBenefit(
                        Benefit("free_gift", "Gift"), FixedAmountReward(Decimal("1"))
                    ),
                )
            },
            "noncashback_reward_not_supported",
        ),
        (
            {
                "benefits": (
                    ValidationBenefit(
                        Benefit("cashback", "Cashback"),
                        ProductSpecificReward((ProductRewardValue(UUID(int=99), Decimal("1")),)),
                    ),
                )
            },
            "product_reward_coverage_mismatch",
        ),
    ],
)
def test_variant_failures(change, code):
    snapshot = valid_snapshot()
    snapshot = replace(snapshot, variants=(replace(snapshot.variants[0], **change),))
    report = validate_promotion_for_publication(snapshot)
    assert code in {i.code for i in report.issues}
    assert not report.can_publish


def test_provenance_reason_preserved_and_multiple_errors():
    snapshot = valid_snapshot()
    source = snapshot.sources[0]
    snapshot = replace(
        snapshot,
        name=" ",
        sources=(
            replace(source, record=replace(source.record, verified_at=None)),
            *snapshot.sources[1:],
        ),
    )
    report = validate_promotion_for_publication(snapshot)
    assert {"missing_promotion_name", "primary_source_unverified"} <= {
        i.code for i in report.issues
    }
    assert report == validate_promotion_for_publication(snapshot)


@pytest.mark.parametrize(
    "end,window,valid",
    [
        (date(2026, 10, 31), RelativeClaimWindow(0, 3652058), False),
        (date.max, RelativeClaimWindow(0, 1), False),
        (date(9999, 12, 30), RelativeClaimWindow(0, 1), True),
        (date(2026, 10, 31), RelativeClaimWindow(0, 30), True),
        (date(2026, 10, 31), RelativeClaimWindow(30, 60), True),
        (None, RelativeClaimWindow(0, 30), False),
        (None, RelativeClaimWindow(0, 0), True),
        (None, FixedClaimWindow(date(2026, 11, 1), date.max), True),
    ],
)
def test_claim_window_representable_for_entire_purchase_range(end, window, valid):
    candidate = replace(valid_snapshot(), purchase_end_date=end, claim_window=window)
    report = validate_promotion_for_publication(candidate)
    assert report.can_publish is valid
    if not valid:
        assert [(i.code, i.path) for i in report.issues] == [
            ("invalid_claim_window", "/promotion/claim_window")
        ]


@pytest.mark.parametrize("name", [None, "", "   "])
def test_incomplete_benefit_name_cannot_publish(name):
    candidate = valid_snapshot()
    variant = candidate.variants[0]
    benefit = replace(variant.benefits[0], benefit=DraftBenefit("cashback", name))
    candidate = replace(candidate, variants=(replace(variant, benefits=(benefit,)),))
    report = validate_promotion_for_publication(candidate)
    assert not report.can_publish
    assert [(i.code, i.path) for i in report.issues] == [
        ("missing_benefit_name", "/promotion/variants/0/benefits/0/name")
    ]
