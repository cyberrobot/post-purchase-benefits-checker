from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.domain.claim_windows import FixedClaimWindow, evaluate_fixed_claim_window
from app.domain.eligibility_result import ClaimWindowStatus, classify_eligibility
from app.domain.eligibility_rules import (
    PurchaseCondition,
    PurchaseConditionRule,
    PurchaseEligibilityFacts,
)
from tests.lg_reference import reference_manifest, validate_manifest


def test_reviewed_manifest_exact_facts_and_evidence():
    f = reference_manifest()
    assert f["reference_version"] == 1
    assert f["manufacturer"] == "LG"
    assert f["product"]["model_or_sku"] == "OLED55G54LW.AEK"
    assert f["retailer"] == "LG.com/UK"
    assert f["benefit"]["type"] == "cashback"
    assert f["benefit"]["reward"] == {"type": "fixed_amount", "amount_gbp": "150.00"}
    assert Decimal(f["benefit"]["reward"]["amount_gbp"]) == Decimal("150.00")
    assert f["purchase_start_date"] == "2025-05-21"
    assert f["purchase_end_date"] == "2025-06-24"
    assert f["claim_window"] == {
        "type": "fixed",
        "start_date": "2025-05-21",
        "end_date": "2025-08-19",
    }
    assert "not the full G5 campaign" in f["coverage"]
    assert f["official_terms_url"] == "https://www.lg.com/uk/tncs/g5-cashback/"
    assert f["claim_url"] == "https://www.lgcashback.com/g5"
    assert f["evidence"]["reviewed_on"] == "2026-10-09"
    clauses = f["evidence"]["clauses"]
    assert "OLED55G54LW.AEK row: GBP 150" in clauses["product_reward"]
    assert "section 22" in clauses["retailer"]
    assert "23:59 GMT" in clauses["claim_window"]
    assert "sections 6–7" in clauses["requirements"]
    assert "not checked" in f["evidence"]["claim_verification"]
    retrieved = datetime.fromisoformat(f["evidence"]["retrieved_at"])
    verified = datetime.fromisoformat(f["evidence"]["verified_at"])
    assert retrieved.tzinfo == UTC and verified >= retrieved
    assert {r["type"] for r in f["requirements"]} == {"receipt", "serial_number"}


@pytest.mark.parametrize(
    "path,value",
    [
        (("purchase_start_date",), "2025-02-30"),
        (("purchase_start_date",), "2025-07-01"),
        (("claim_window", "start_date"), "2025-08-20"),
        (("claim_window", "end_date"), "2025-13-01"),
        (("claim_window", "type"), "relative"),
        (("benefit", "type"), "free_gift"),
        (("benefit", "reward", "amount_gbp"), 150.0),
        (("benefit", "reward", "amount_gbp"), "151.00"),
        (("product", "model_or_sku"), "OLED55G54LW"),
        (("retailer",), "Another retailer"),
        (("official_terms_url",), None),
        (("official_terms_url",), "http://localhost/terms"),
        (("claim_url",), "file:///tmp/claim"),
        (("evidence",), None),
        (("requirements",), []),
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


@pytest.mark.parametrize("missing", ["official_terms_url", "evidence"])
def test_omitted_evidence_rejected(missing):
    f = deepcopy(reference_manifest())
    del f[missing]
    with pytest.raises(ValueError, match="reviewed"):
        validate_manifest(f)


@pytest.mark.parametrize(
    "day,status",
    [
        (date(2025, 5, 20), ClaimWindowStatus.NOT_YET_OPEN),
        (date(2025, 5, 21), ClaimWindowStatus.OPEN),
        (date(2025, 8, 19), ClaimWindowStatus.OPEN),
        (date(2025, 8, 20), ClaimWindowStatus.EXPIRED),
    ],
)
def test_fixed_claim_window_inclusive_calendar_boundaries(day, status):
    f = reference_manifest()["claim_window"]
    window = FixedClaimWindow(
        date.fromisoformat(f["start_date"]), date.fromisoformat(f["end_date"])
    )
    result = evaluate_fixed_claim_window(window, day)
    assert (result.opens_on, result.deadline_on, result.status) == (
        date(2025, 5, 21),
        date(2025, 8, 19),
        status,
    )


def test_validation_delay_is_evidence_and_does_not_delay_claim_submission():
    f = reference_manifest()
    assert f["evidence"]["validation_delay_days"] == 30
    assert "processing/validation" in f["evidence"]["clauses"]["validation_delay"]
    assert "not a submission-opening delay" in f["evidence"]["clauses"]["validation_delay"]
    assert f["claim_window"]["start_date"] == f["purchase_start_date"]
    assert not {"start_offset_days", "end_offset_days"}.intersection(f["claim_window"])


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
        uuid4(), uuid4(), uuid4(), date(2025, 5, 21), condition=condition
    )
    evaluation = PurchaseConditionRule({PurchaseCondition.NEW}).evaluate(facts)
    result = classify_eligibility((evaluation,), ClaimWindowStatus.OPEN)
    assert result.classification == classification
    assert [r.code for r in result.reasons] == [reason]


def test_reviewed_pin_ignores_json_formatting_and_key_order():
    import json

    f = reference_manifest()
    reordered = {key: f[key] for key in reversed(f)}
    assert validate_manifest(json.loads(json.dumps(reordered, indent=4))) == f
    assert reference_manifest() == f
