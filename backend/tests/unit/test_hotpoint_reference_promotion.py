import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest

from app.domain.claim_windows import (
    ClaimWindowStatus,
    FixedClaimWindow,
    evaluate_fixed_claim_window,
)
from app.domain.rewards import FixedAmountReward, calculate_reward
from tests.hotpoint_reference import reference_manifest, validate_manifest


def test_manifest_exact_wren_facts_evidence_and_unmodelled_delay():
    f = reference_manifest()
    assert f["reference_version"] == 1
    assert f["evidence_status"] == "verified"
    assert f["manufacturer"] == "Hotpoint"
    assert f["retailer"] == "Wren"
    assert f["product"]["model_or_sku"] == "H7IC16M6 UK"
    assert f["benefit"]["reward"]["amount_gbp"] == "75.00"
    assert f["purchase_start_date"] == "2026-05-05"
    assert f["purchase_end_date"] == "2026-06-12"
    assert f["claim_window"] == {
        "type": "fixed",
        "minimum_days_after_purchase": 30,
        "start_date": "2026-06-04",
        "end_date": "2026-12-04",
    }
    assert {r["type"] for r in f["requirements"]} == {"receipt", "serial_number", "registration"}
    evidence = f["evidence"]
    assert evidence["section_heading"] == "HOTPOINT CASHBACK PROMOTION - WREN"
    assert evidence["clause_map"]["retailer"] == "Wren clause 13"
    assert evidence["clause_map"]["model_and_reward"] == "Wren clause 4, built-in dishwasher row"
    assert datetime.fromisoformat(evidence["verified_at"]) >= datetime.fromisoformat(
        evidence["retrieved_at"]
    )
    assert "No user-specific" in evidence["claim_portal_observation"]
    assert f["claim_delay_limitation"]["minimum_days_after_purchase"] == 30
    assert f["claim_delay_limitation"]["authoritative_runtime_rule"] is False
    assert f["claim_delay_limitation"]["production_publication_permitted"] is False


@pytest.mark.parametrize(
    "path,value",
    [
        (("product", "model_or_sku"), "H7IC16M6"),
        (("retailer",), "Currys"),
        (("benefit", "reward", "amount_gbp"), "100.00"),
        (("claim_window", "end_date"), "2026-07-26"),
        (("official_terms_url",), "https://example.com/terms"),
        (("claim_url",), "http://promo.hotpoint.co.uk/"),
        (("evidence_status",), "unverified"),
        (("evidence", "verified_at"), None),
        (("evidence", "section_heading"), "HOTPOINT CASHBACK PROMOTION"),
        (("claim_delay_limitation", "minimum_days_after_purchase"), 0),
        (("requirements",), []),
        (("purchase_start_date",), False),
    ],
)
def test_semantic_pin_rejects_changed_facts_evidence_or_limitations(path, value):
    changed = deepcopy(reference_manifest())
    target = changed
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match="pinned"):
        validate_manifest(changed)


@pytest.mark.parametrize(
    "value", [None, [], {}, {"evidence_status": "verified"}, {"value": float("nan")}]
)
def test_missing_malformed_evidence_is_never_repaired(value):
    with pytest.raises(ValueError):
        validate_manifest(value)


def test_json_formatting_and_key_order_preserve_semantic_pin():
    f = reference_manifest()
    assert validate_manifest(json.loads(json.dumps(f, sort_keys=True, indent=4))) == f


@pytest.mark.parametrize("price", [None, Decimal("0.00"), Decimal("1.00"), Decimal("2000.00")])
def test_fixed_reward_does_not_require_purchase_price(price):
    assert calculate_reward(FixedAmountReward(Decimal("75.00")), purchase_price=price) == Decimal(
        "75.00"
    )


@pytest.mark.parametrize(
    "as_of,status",
    [
        (date(2026, 6, 3), ClaimWindowStatus.NOT_YET_OPEN),
        (date(2026, 6, 4), ClaimWindowStatus.OPEN),
        (date(2026, 12, 4), ClaimWindowStatus.OPEN),
        (date(2026, 12, 5), ClaimWindowStatus.EXPIRED),
    ],
)
def test_fixed_base_window_inclusive_edges(as_of, status):
    assert (
        evaluate_fixed_claim_window(
            FixedClaimWindow(date(2026, 6, 4), date(2026, 12, 4)), as_of
        ).status
        == status
    )


@pytest.mark.parametrize(
    "purchase,first,last_waiting",
    [
        (date(2026, 5, 5), date(2026, 6, 4), date(2026, 6, 3)),
        (date(2026, 6, 12), date(2026, 7, 12), date(2026, 7, 11)),
    ],
)
def test_limitation_regression_official_arithmetic_is_evidence_only(purchase, first, last_waiting):
    f = reference_manifest()
    earliest = max(
        date.fromisoformat(f["claim_window"]["start_date"]),
        purchase + timedelta(days=f["claim_delay_limitation"]["minimum_days_after_purchase"]),
    )
    assert earliest == first
    assert earliest - timedelta(days=1) == last_waiting
    assert f["claim_delay_limitation"]["status"] == "unmodelled"
