from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.claim_windows import RelativeClaimWindow, evaluate_relative_claim_window
from app.domain.eligibility_result import ClaimWindowStatus, classify_eligibility
from app.domain.eligibility_rules import (
    PurchaseCondition,
    PurchaseConditionRule,
    PurchaseEligibilityFacts,
)
from tests.samsung_reference import reference_manifest, validate_manifest


def test_reviewed_manifest_exact_facts():
    f = reference_manifest()
    assert f["reference_version"] == 1
    assert f["product"]["model_or_sku"] == "SM-R640"
    assert Decimal(f["benefit"]["reward"]["amount_gbp"]) == Decimal("50.00")
    assert date.fromisoformat(f["purchase_start_date"]) == date(2026, 6, 3)
    assert date.fromisoformat(f["purchase_end_date"]) == date(2026, 6, 23)
    assert "not the full campaign" in f["coverage"]


@pytest.mark.parametrize(
    "path,value",
    [
        (("purchase_start_date",), "2026-02-30"),
        (("benefit", "type"), "free_gift"),
        (("benefit", "reward", "amount_gbp"), 50.0),
        (("benefit", "reward", "amount_gbp"), "51.00"),
        (("claim_window", "end_offset_days"), 30),
        (("product", "model_or_sku"), "SM-R630"),
        (("official_terms_url",), "http://localhost/terms"),
        (("evidence",), None),
        (("unexpected",), "unreviewed"),
    ],
)
def test_unreviewed_or_malformed_manifest_rejected(path, value):
    f = deepcopy(reference_manifest())
    target = f
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match="reviewed"):
        validate_manifest(f)


@pytest.mark.parametrize(
    "purchase,deadline",
    [(date(2026, 6, 3), date(2026, 7, 2)), (date(2026, 6, 23), date(2026, 7, 22))],
)
def test_thirty_days_includes_purchase_day(purchase, deadline):
    f = reference_manifest()["claim_window"]
    window = RelativeClaimWindow(f["start_offset_days"], f["end_offset_days"])
    for day in (purchase, deadline):
        result = evaluate_relative_claim_window(window, purchase, day)
        assert (result.opens_on, result.deadline_on, result.status) == (
            purchase,
            deadline,
            ClaimWindowStatus.OPEN,
        )
    assert (
        evaluate_relative_claim_window(window, purchase, deadline + timedelta(days=1)).status
        == ClaimWindowStatus.EXPIRED
    )


@pytest.mark.parametrize(
    "condition,classification,reason",
    [
        (PurchaseCondition.REFURBISHED, "NOT_ELIGIBLE", "condition_mismatch"),
        (None, "POTENTIALLY_ELIGIBLE", "condition_unknown"),
    ],
)
def test_new_only_domain_rule_is_separate_from_public_five_field_request(
    condition, classification, reason
):
    facts = PurchaseEligibilityFacts(
        uuid4(), uuid4(), uuid4(), date(2026, 6, 3), condition=condition
    )
    evaluation = PurchaseConditionRule({PurchaseCondition.NEW}).evaluate(facts)
    result = classify_eligibility((evaluation,), ClaimWindowStatus.OPEN)
    assert result.classification == classification
    assert [r.code for r in result.reasons] == [reason]
