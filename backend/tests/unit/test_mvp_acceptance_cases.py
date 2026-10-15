"""Validate independent expectations against reviewed data, without application output."""

import pytest

from tests.acceptance.cases import CASES


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.brand.lower())
def test_pinned_acceptance_identity_reward_and_requirements(case):
    manifest = case.manifest
    assert (case.brand, case.model, case.retailer) == (
        manifest["manufacturer"],
        manifest["product"]["model_or_sku"],
        manifest["retailer"],
    )
    assert case.reward == manifest["benefit"]["reward"]["amount_gbp"]
    expected_types = {"receipt", "serial_number"}
    if case.brand == "Hotpoint":
        expected_types.add("registration")
    assert {r["type"] for r in manifest["requirements"]} == expected_types
    assert manifest["purchase_start_date"] <= case.purchase <= manifest["purchase_end_date"]
    if case.brand != "Samsung":
        assert case.opens == manifest["claim_window"]["start_date"]
        assert case.deadline == manifest["claim_window"]["end_date"]


def test_matrix_is_five_distinct_manufacturers_and_legitimate_opening_cases():
    assert [c.brand for c in CASES] == ["Samsung", "LG", "Hisense", "Hotpoint", "Sony"]
    assert len({(c.brand, c.model, c.retailer) for c in CASES}) == 5
    assert {c.brand for c in CASES if c.not_yet_open is None} == {"Samsung", "LG"}
    assert {
        c.brand
        for c in CASES
        if c.manifest.get("claim_delay_limitation", {}).get("production_publication_permitted")
        is False
    } == {"Hotpoint", "Sony"}
