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


def test_manifest_records_verified_hisense_reference_facts_and_provenance():
    f = reference_manifest()
    assert f["evidence_status"] == "verified"
    assert f["manufacturer"] == "Hisense"
    assert f["product"]["model_or_sku"] == "WF7I1248BBR"
    assert f["retailer"] == "Currys"
    assert Decimal(f["benefit"]["reward"]["amount_gbp"]) == Decimal("100.00")
    assert f["purchase_start_date"] == "2026-09-09"
    assert f["purchase_end_date"] == "2026-10-27"
    assert f["claim_window"] == {
        "type": "fixed",
        "start_date": "2026-11-27",
        "end_date": "2026-12-24",
    }
    evidence = f["evidence"]
    assert evidence["terms_version"] == "19 August 2026"
    assert evidence["retrieved_at"] == "2026-10-12T13:57:18Z"
    assert evidence["verified_at"] == "2026-10-12T15:14:03Z"
    assert evidence["capture"]["sha256"] == (
        "7d656fa2df22258b9bbc56a9bffd57e752d1b201b972fe154a57483f9a059add"
    )
    assert any("Annex 1" in item for item in evidence["sections_reviewed"])
    assert any("Annex 2" in item for item in evidence["sections_reviewed"])
    assert {r["type"] for r in f["requirements"]} == {"receipt", "serial_number"}
    assert evidence["supporting_source"]["retrieved_at"] is None
    assert "not independently accessed" in evidence["claim_portal_observation"]
    assert "not evaluated" in f["limitations"][1]


def test_manifest_rejects_semantic_changes_and_forged_verification():
    f = reference_manifest()
    for path, value in (
        (("product", "model_or_sku"), "WF7I1248BBA"),
        (("retailer",), "Amazon"),
        (("benefit", "reward", "amount_gbp"), "150.00"),
        (("claim_window", "start_date"), "2026-11-26"),
        (("official_terms_url",), "http://example.com/terms"),
        (("evidence", "verified_at"), "2026-10-09T14:53:52Z"),
    ):
        changed = deepcopy(f)
        target = changed
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = value
        with pytest.raises(ValueError, match="pinned"):
            validate_manifest(changed)


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
def test_verified_fixed_claim_window_inclusive_boundaries(as_of, status):
    result = evaluate_fixed_claim_window(
        FixedClaimWindow(date(2026, 11, 27), date(2026, 12, 24)), as_of
    )
    assert result.status == status
    assert result.opens_on == date(2026, 11, 27)
    assert result.deadline_on == date(2026, 12, 24)


@pytest.mark.parametrize("price", [None, Decimal("0.00"), Decimal("1.00"), Decimal("2000.00")])
def test_verified_fixed_reward_is_exact_and_independent_of_purchase_price(price):
    from app.domain.rewards import FixedAmountReward, calculate_reward

    amount = Decimal(reference_manifest()["benefit"]["reward"]["amount_gbp"])
    assert calculate_reward(FixedAmountReward(amount), purchase_price=price) == Decimal("100.00")
