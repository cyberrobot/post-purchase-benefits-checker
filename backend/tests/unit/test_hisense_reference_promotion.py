import json
from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from app.domain.claim_windows import (
    ClaimWindowStatus,
    FixedClaimWindow,
    evaluate_fixed_claim_window,
)
from tests.hisense_reference import reference_manifest, validate_manifest


def test_review_records_exact_facts_and_full_authority():
    f = reference_manifest()
    assert f["evidence_status"] == "verified_reference"
    assert f["product"]["model_or_sku"] == "WF7I1248BBR"
    assert f["retailer"] == "Currys"
    assert Decimal(f["benefit"]["reward"]["amount_gbp"]) == Decimal("100.00")
    assert f["claim_window"] == {
        "type": "fixed",
        "start_date": "2026-11-27",
        "end_date": "2026-12-24",
    }
    terms = f["evidence"]["observations"][0]
    assert terms["verified_at"] == "2026-10-09T14:53:52Z"
    assert {"Annex 1", "Annex 2"} <= set(terms["sections_reviewed"])
    assert {r["type"] for r in f["requirements"]} == {"receipt", "serial_number"}
    receipt = next(r["description"] for r in f["requirements"] if r["type"] == "receipt")
    assert all(
        field in receipt.lower()
        for field in ("product/model", "purchase date", "purchase price", "participating retailer")
    )
    assert f["evidence"]["historical_observations"][0]["verified_at"] is None


@pytest.mark.parametrize(
    "path,value",
    [
        (("product", "model_or_sku"), "WF7I1248BBA"),
        (("retailer",), "Amazon"),
        (("benefit", "reward", "amount_gbp"), "150.00"),
        (("claim_window", "start_date"), "2026-10-27"),
        (("official_terms_url",), "http://example.com/terms"),
        (("evidence_status",), "verified"),
    ],
)
def test_semantic_edits_and_unverified_promotion_rejected(path, value):
    f = deepcopy(reference_manifest())
    target = f
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match="pinned|evidence"):
        validate_manifest(f)


def test_manifest_json_formatting_and_key_order_do_not_change_pin():
    f = reference_manifest()
    assert validate_manifest(json.loads(json.dumps(f, indent=2, sort_keys=True))) == f


@pytest.mark.parametrize(
    "as_of,status",
    [
        (date(2026, 11, 26), ClaimWindowStatus.NOT_YET_OPEN),
        (date(2026, 11, 27), ClaimWindowStatus.OPEN),
        (date(2026, 12, 24), ClaimWindowStatus.OPEN),
        (date(2026, 12, 25), ClaimWindowStatus.EXPIRED),
    ],
)
def test_fixed_claim_window_inclusive_boundaries(as_of, status):
    result = evaluate_fixed_claim_window(
        FixedClaimWindow(date(2026, 11, 27), date(2026, 12, 24)), as_of
    )
    assert result.status == status
    assert result.opens_on == date(2026, 11, 27)
    assert result.deadline_on == date(2026, 12, 24)


@pytest.mark.parametrize(
    "path,value",
    [
        (("reference_version",), 2),
        (("purchase_start_date",), "2026-13-01"),
        (("purchase_end_date",), "2026-09-08"),
        (("claim_window", "type"), "relative"),
        (("claim_window", "end_date"), "2026-11-26"),
        (("benefit", "reward", "amount_gbp"), 100.0),
        (("claim_url",), "javascript:alert(1)"),
        (("requirements",), []),
        (("limitations",), []),
    ],
)
def test_unreviewed_rule_and_evidence_changes_rejected(path, value):
    manifest = deepcopy(reference_manifest())
    target = manifest
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ValueError, match="pinned"):
        validate_manifest(manifest)


@pytest.mark.parametrize("change", ["missing", "extra", "verification", "timestamp"])
def test_manifest_schema_and_evidence_are_pinned(change):
    manifest = deepcopy(reference_manifest())
    if change == "missing":
        del manifest["product"]["model_or_sku"]
    elif change == "extra":
        manifest["benefit"]["reward"]["currency"] = "GBP"
    elif change == "verification":
        manifest["evidence"]["observations"][0]["verified_at"] = None
    else:
        manifest["evidence"]["observations"][2]["retrieved_at"] = "2026-10-10T12:00:00Z"
    with pytest.raises(ValueError, match="pinned"):
        validate_manifest(manifest)


@pytest.mark.parametrize("price", [None, Decimal("0.00"), Decimal("1.00"), Decimal("2000.00")])
def test_proposed_fixed_reward_is_exact_and_independent_of_price(price):
    from app.domain.rewards import FixedAmountReward, calculate_reward

    amount = Decimal(reference_manifest()["benefit"]["reward"]["amount_gbp"])
    assert calculate_reward(FixedAmountReward(amount), purchase_price=price) == Decimal("100.00")
