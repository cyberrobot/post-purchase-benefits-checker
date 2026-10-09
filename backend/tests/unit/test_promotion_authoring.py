from copy import deepcopy
from uuid import UUID

import pytest

from app.application.promotion_authoring import (
    CandidateInputError,
    parse_candidate_promotion,
    validate_candidate_promotion,
)


def document():
    return {
        "schema_version": 1,
        "promotion": {
            "manufacturer_id": str(UUID(int=1)),
            "name": "Campaign",
            "slug": "campaign",
            "purchase_start_date": "2026-10-01",
            "claim_window": {"type": "relative", "start_offset_days": 0, "end_offset_days": 30},
            "variants": [
                {
                    "code": "all",
                    "retailer_id": None,
                    "product_ids": [str(UUID(int=2))],
                    "benefits": [
                        {
                            "type": "cashback",
                            "name": "Cashback",
                            "reward": {"type": "fixed_amount", "amount_gbp": "50.00"},
                        }
                    ],
                }
            ],
            "sources": [
                {"source_id": str(UUID(int=3)), "role": "primary"},
                {"source_id": str(UUID(int=4)), "role": "claim"},
            ],
        },
    }


def test_round_trip_and_preflight_never_authorizes():
    raw = document()
    before = deepcopy(raw)
    parsed = parse_candidate_promotion(raw)
    dumped = parsed.model_dump(mode="json")
    assert parse_candidate_promotion(dumped).model_dump(mode="json") == dumped
    assert raw == before
    assert dumped["promotion"]["variants"][0]["benefits"][0]["reward"]["amount_gbp"] == "50.00"
    report = validate_candidate_promotion(parsed)
    assert [i.code for i in report.issues] == ["unresolved_references"]
    assert not report.can_publish


def test_partial_draft():
    report = validate_candidate_promotion(
        parse_candidate_promotion({"schema_version": 1, "promotion": {}})
    )
    assert "missing_manufacturer" in {i.code for i in report.issues}
    assert not report.can_publish


@pytest.mark.parametrize("amount", [50.0, "NaN", "Infinity", "1e2", "1.001", "0", "-1"])
def test_rejects_invalid_money(amount):
    raw = document()
    raw["promotion"]["variants"][0]["benefits"][0]["reward"]["amount_gbp"] = amount
    with pytest.raises(CandidateInputError) as error:
        parse_candidate_promotion(raw)
    assert error.value.report.issues[0].path.endswith("/reward/amount_gbp")
    assert str(amount) not in str(error.value)


def test_invalid_percentage_value_path_retains_field_name():
    raw = document()
    raw["promotion"]["variants"][0]["benefits"][0]["reward"] = {
        "type": "percentage",
        "percentage": "100.0001",
    }
    with pytest.raises(CandidateInputError) as error:
        parse_candidate_promotion(raw)
    assert error.value.report.issues[0].path.endswith("/percentage")


@pytest.mark.parametrize("field", ["fixed", "relative"])
def test_unsupported_property_matching_discriminator_is_preserved(field):
    raw = document()
    raw["promotion"][field] = "unexpected"
    with pytest.raises(CandidateInputError) as error:
        parse_candidate_promotion(raw)
    assert f"/promotion/{field}" in {issue.path for issue in error.value.report.issues}


@pytest.mark.parametrize(
    "window",
    [
        {"type": "fixed", "start_date": "2026-11-01", "end_date": "2026-11-02", "fixed": True},
        {"type": "relative", "start_offset_days": 0, "end_offset_days": 30, "relative": True},
    ],
)
def test_unsupported_property_matching_window_tag_is_preserved(window):
    raw = document()
    raw["promotion"]["claim_window"] = window
    with pytest.raises(CandidateInputError) as error:
        parse_candidate_promotion(raw)
    assert "/promotion/claim_window/" + window["type"] in {
        issue.path for issue in error.value.report.issues
    }


@pytest.mark.parametrize(
    "change,path",
    [
        (lambda d: d.update(schema_version=True), "/schema_version"),
        (lambda d: d["promotion"].update(status="active"), "/promotion/status"),
        (lambda d: d["promotion"].update(country="UK"), "/promotion/country"),
        (lambda d: d["promotion"].update(manufacturer_id="bogus"), "/promotion/manufacturer_id"),
        (
            lambda d: d["promotion"].update(purchase_start_date="2026-02-30"),
            "/promotion/purchase_start_date",
        ),
        (
            lambda d: d["promotion"]["variants"][0].pop("retailer_id"),
            "/promotion/variants/0/retailer_id",
        ),
        (
            lambda d: d["promotion"]["claim_window"].update(start_offset_days=True),
            "/promotion/claim_window/start_offset_days",
        ),
        (
            lambda d: d["promotion"]["claim_window"].update(start_date="2026-10-01"),
            "/promotion/claim_window/start_date",
        ),
        (lambda d: d["promotion"].update(name="x" * 256), "/promotion/name"),
    ],
)
def test_path_aware_rejection(change, path):
    raw = document()
    change(raw)
    with pytest.raises(CandidateInputError) as error:
        parse_candidate_promotion(raw)
    assert path in {i.path for i in error.value.report.issues}


def test_duplicate_content_reports_without_deduplication():
    raw = document()
    variant = raw["promotion"]["variants"][0]
    variant["product_ids"] *= 2
    raw["promotion"]["variants"] *= 2
    raw["promotion"]["sources"] *= 2
    report = validate_candidate_promotion(parse_candidate_promotion(raw))
    assert {
        "duplicate_product",
        "duplicate_variant_code",
        "duplicate_source_link",
        "ambiguous_primary_source",
    } <= {i.code for i in report.issues}
    assert report == validate_candidate_promotion(parse_candidate_promotion(raw))


@pytest.mark.parametrize(
    "window",
    [
        {"type": "fixed", "start_date": "2026-11-01", "end_date": "2026-11-01"},
        {"type": "relative", "start_offset_days": 0, "end_offset_days": 0},
    ],
)
def test_window_forms(window):
    raw = document()
    raw["promotion"]["claim_window"] = window
    assert [
        i.code for i in validate_candidate_promotion(parse_candidate_promotion(raw)).issues
    ] == ["unresolved_references"]


def test_bounds():
    raw = document()
    raw["promotion"]["variants"] *= 51
    with pytest.raises(CandidateInputError):
        parse_candidate_promotion(raw)
    raw = document()
    raw["promotion"]["variants"][0]["benefits"][0]["description"] = "x" * 2001
    with pytest.raises(CandidateInputError):
        parse_candidate_promotion(raw)


@pytest.mark.parametrize(
    "reward",
    [
        {"type": "fixed_amount", "amount_gbp": "50.00"},
        {"type": "percentage", "percentage": "10.5000"},
        {
            "type": "product_specific",
            "values": [{"product_id": str(UUID(int=2)), "amount_gbp": "40.00"}],
        },
    ],
)
def test_all_reward_types(reward):
    raw = document()
    raw["promotion"]["variants"][0]["benefits"][0]["reward"] = reward
    parsed = parse_candidate_promotion(raw)
    assert [i.code for i in validate_candidate_promotion(parsed).issues] == [
        "unresolved_references"
    ]
    assert (
        parsed.model_dump(mode="json")["promotion"]["variants"][0]["benefits"][0]["reward"]
        == reward
    )


def test_all_benefit_and_requirement_types():
    from app.domain.requirements import RequirementType

    raw = document()
    variant = raw["promotion"]["variants"][0]
    variant["benefits"] += [
        {"type": "free_gift", "name": "Gift"},
        {"type": "extended_warranty", "name": "Warranty"},
    ]
    variant["requirements"] = [
        {"type": kind.value, "description": "Instruction"} for kind in RequirementType
    ]
    parsed = parse_candidate_promotion(raw)
    assert [i.code for i in validate_candidate_promotion(parsed).issues] == [
        "unresolved_references"
    ]


def test_unsupported_enum_and_array_and_depth_limits():
    for mutate in (
        lambda d: d["promotion"]["variants"][0]["benefits"][0].update(type="coupon"),
        lambda d: d["promotion"]["variants"][0].update(product_ids=[str(UUID(int=2))] * 201),
        lambda d: d["promotion"].update(sources=d["promotion"]["sources"] * 16),
        lambda d: d["promotion"]["variants"][0].update(
            benefits=d["promotion"]["variants"][0]["benefits"] * 21
        ),
        lambda d: d["promotion"]["variants"][0].update(requirements=[{"type": "receipt"}] * 31),
    ):
        raw = document()
        mutate(raw)
        with pytest.raises(CandidateInputError):
            parse_candidate_promotion(raw)
    value = {}
    for _ in range(14):
        value = {"nested": value}
    with pytest.raises(CandidateInputError):
        parse_candidate_promotion(value)
