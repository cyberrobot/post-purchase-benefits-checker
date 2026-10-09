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


def test_candidate_records_exact_proposed_facts_and_evidence_gap():
    f = reference_manifest()
    assert f["evidence_status"] == "unverified_review_candidate"
    assert f["product"]["model_or_sku"] == "WF7I1248BBR"
    assert f["retailer"] == "Currys"
    assert Decimal(f["benefit"]["reward"]["amount_gbp"]) == Decimal("100.00")
    assert f["claim_window"] == {
        "type": "fixed",
        "start_date": "2026-11-27",
        "end_date": "2026-12-24",
    }
    terms = f["evidence"]["observations"][0]
    assert terms["retrieval_status"] == "blocked_by_javascript_bot_challenge"
    assert terms["verified_at"] is None
    assert "No facts are verified" in terms["outcome"]
    assert not f["requirements"]
    assert any("UNVERIFIED" in item for item in f["limitations"])


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
