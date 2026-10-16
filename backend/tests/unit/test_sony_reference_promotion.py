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
from tests.sony_reference import reference_manifest, validate_manifest


def test_manifest_exact_sony_facts_evidence_and_unmodelled_delay():
    f = reference_manifest()
    assert f["reference_version"] == 1
    assert f["evidence_status"] == "verified"
    assert f["manufacturer"] == "Sony"
    assert f["retailer"] == "Currys - UK"
    assert f["product"]["model_or_sku"] == "K55XR75M2B"
    assert f["benefit"]["reward"]["amount_gbp"] == "150.00"
    assert f["purchase_start_date"] == "2026-09-30"
    assert f["purchase_end_date"] == "2026-10-27"
    assert f["claim_window"] == {
        "type": "fixed",
        "minimum_days_after_purchase": 35,
        "start_date": "2026-11-04",
        "end_date": "2026-12-31",
    }
    assert {r["type"] for r in f["requirements"]} == {"receipt", "serial_number"}
    evidence = f["evidence"]
    assert evidence["section_heading"] == "Sony UK TV Autumn Cashback 2026"
    assert (
        evidence["clause_map"]["retailer"]
        == "UK authorised-dealer PDF, page 3, Currys - UK entry; terms section 11"
    )
    assert (
        evidence["clause_map"]["model_and_reward"]
        == "Terms section 6, page 1, K55XR75M2B row, GBP column"
    )
    assert datetime.fromisoformat(evidence["verified_at"]) >= datetime.fromisoformat(
        evidence["retrieved_at"]
    )
    assert "No customer claim" in evidence["claim_portal_observation"]
    assert f["claim_delay_limitation"]["minimum_days_after_purchase"] == 35
    assert f["claim_delay_limitation"]["authoritative_runtime_rule"] is False
    assert f["claim_delay_limitation"]["production_publication_permitted"] is False


@pytest.mark.parametrize(
    "path,value",
    [
        (("manufacturer",), "Other brand"),
        (("product", "model_or_sku"), "K55XR75M2PB"),
        (("product", "model_or_sku"), "K55XR75M2"),
        (("purchase_start_date",), "2026-10-01"),
        (("purchase_end_date",), "2026-10-28"),
        (("claim_window", "start_date"), "2026-11-03"),
        (("dealer_list_url",), "https://example.com/dealers"),
        (("faq_url",), "https://example.com/faq"),
        (("evidence", "retrieved_at"), None),
        (("evidence", "terms_version"), "unreviewed"),
        (("evidence", "faq_conflict"), ""),
        (("limitations",), []),
        (("claim_delay_limitation", "production_publication_permitted"), True),
        (("retailer",), "Currys"),
        (("benefit", "reward", "amount_gbp"), "100.00"),
        (("claim_window", "end_date"), "2026-07-26"),
        (("official_terms_url",), "https://example.com/terms"),
        (("claim_url",), "http://www.sony.co.uk/cashback/braviaautumn2026"),
        (("evidence_status",), "unverified"),
        (("evidence", "verified_at"), None),
        (("evidence", "section_heading"), "UNREVIEWED SONY CAMPAIGN"),
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
    assert calculate_reward(FixedAmountReward(Decimal("150.00")), purchase_price=price) == Decimal(
        "150.00"
    )


@pytest.mark.parametrize(
    "as_of,status",
    [
        (date(2026, 11, 3), ClaimWindowStatus.NOT_YET_OPEN),
        (date(2026, 11, 4), ClaimWindowStatus.OPEN),
        (date(2026, 12, 31), ClaimWindowStatus.OPEN),
        (date(2027, 1, 1), ClaimWindowStatus.EXPIRED),
    ],
)
def test_fixed_base_window_inclusive_edges(as_of, status):
    assert (
        evaluate_fixed_claim_window(
            FixedClaimWindow(date(2026, 11, 4), date(2026, 12, 31)), as_of
        ).status
        == status
    )


@pytest.mark.parametrize(
    "purchase,first,last_waiting",
    [
        (date(2026, 9, 30), date(2026, 11, 4), date(2026, 11, 3)),
        (date(2026, 10, 27), date(2026, 12, 1), date(2026, 11, 30)),
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


def test_malformed_local_json_is_rejected(tmp_path, monkeypatch):
    from tests import sony_reference

    broken = tmp_path / "broken.json"
    broken.write_text("{")
    monkeypatch.setattr(sony_reference, "MANIFEST", broken)
    with pytest.raises(ValueError):
        reference_manifest()


def test_late_purchase_base_window_false_positive_risk_remains_explicit():
    f = reference_manifest()
    assert date(2026, 11, 4) < date(2026, 10, 27) + timedelta(days=35)
    assert "2026-11-30" in f["claim_delay_limitation"]["unsafe_historical_interval"]
    assert "false-positive ELIGIBLE" in " ".join(f["limitations"])
    assert f["claim_delay_limitation"]["production_publication_permitted"] is False


def test_descriptive_restrictions_and_separate_source_observations():
    f = reference_manifest()
    assert f["evidence"]["terms_version"] == "26/08/2026; four pages"
    assert f["evidence"]["dealer_list_version"] == "28/09/2026"
    assert f["evidence"]["supporting_source"]["source_type"] == "pdf"
    for observation in (f["evidence"], f["evidence"]["supporting_source"]):
        assert datetime.fromisoformat(observation["retrieved_at"]).utcoffset() == timedelta(0)
        assert datetime.fromisoformat(observation["verified_at"]) >= datetime.fromisoformat(
            observation["retrieved_at"]
        )
    descriptions = " ".join(r["description"] for r in f["requirements"])
    for required in (
        "Original receipt/invoice",
        "order date controls",
        "screen photo displaying serial/device ID OR back-of-TV photo",
        "model, manufacturing date and serial",
    ):
        assert required in descriptions
    restrictions = " ".join(f["evidence"]["exclusions_and_limitations"] + f["limitations"])
    for required in (
        "original owner",
        "age 18+",
        "returned/refurbished",
        "My Sony account",
        "one per model, two total",
        "CET",
        "not satisfied user facts",
    ):
        assert required in restrictions
    assert "one claim per individual model, two total" in f["evidence"]["faq_conflict"]


def test_source_mapping_uses_synthetic_distinct_observation_times():
    from tests.sony_reference import source_observations

    synthetic = deepcopy(reference_manifest())
    synthetic["evidence"]["supporting_source"].update(
        retrieved_at="2000-01-01T12:00:00Z", verified_at="2000-01-02T12:00:00Z"
    )
    observations = source_observations(synthetic)
    assert observations["supporting"] == synthetic["evidence"]["supporting_source"]
    assert observations["primary"]["retrieved_at"] == synthetic["evidence"]["retrieved_at"]
    assert observations["claim"]["verified_at"] == synthetic["evidence"]["verified_at"]
    assert observations["supporting"]["retrieved_at"] != observations["primary"]["retrieved_at"]
    # Pure synthetic mapping does not make the modified object a reviewed manifest.
    with pytest.raises(ValueError, match="pinned"):
        validate_manifest(synthetic)


@pytest.mark.parametrize("role", ["primary", "supporting"])
@pytest.mark.parametrize(
    "retrieved,verified",
    [
        ("not-a-date", "2000-01-02T12:00:00Z"),
        ("2000-01-01T12:00:00", "2000-01-02T12:00:00Z"),
        ("2000-01-01T12:00:00Z", "2000-01-02T12:00:00"),
        ("2000-01-02T12:00:00Z", "2000-01-01T12:00:00Z"),
        ("2000-01-01T12:00:00Z", None),
    ],
)
def test_source_mapping_rejects_invalid_synthetic_timestamps(role, retrieved, verified):
    from tests.sony_reference import source_observations

    synthetic = deepcopy(reference_manifest())
    target = (
        synthetic["evidence"] if role == "primary" else synthetic["evidence"]["supporting_source"]
    )
    target.update(retrieved_at=retrieved, verified_at=verified)
    with pytest.raises(ValueError, match="timestamp|verification"):
        source_observations(synthetic)


@pytest.mark.parametrize(
    "field,value", [("url", "https://example.com/unreviewed.pdf"), ("source_type", "web_page")]
)
def test_source_mapping_rejects_inconsistent_supporting_evidence(field, value):
    from tests.sony_reference import source_observations

    synthetic = deepcopy(reference_manifest())
    synthetic["evidence"]["supporting_source"][field] = value
    with pytest.raises(ValueError, match="Inconsistent supporting dealer evidence"):
        source_observations(synthetic)
