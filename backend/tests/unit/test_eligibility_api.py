import json
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api import eligibility as api
from app.application.identity_matching import IdentityPersistenceError
from app.application.promotion_candidate_matching import (
    ResolvedPurchaseIdentity,
    UnresolvedPurchaseIdentity,
)
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check_details import (
    CheckPurchaseBenefit,
    CheckPurchasePromotionResult,
    CheckPurchaseResult,
    NoMatchReason,
    PublishedPromotionDataError,
    RewardUnavailableReason,
)
from app.core.config import Settings
from app.domain.benefits import Benefit
from app.domain.claim_windows import ClaimWindowEvaluation
from app.domain.eligibility_result import (
    ClaimWindowStatus,
    EligibilityClassification,
    classify_eligibility,
)
from app.domain.eligibility_rules import RuleEvaluation, RuleKind, RuleReasonCode, RuleStatus
from app.domain.identity_normalisation import MatchStatus
from app.domain.promotion_lifecycle import PromotionStatus
from app.domain.promotion_provenance import PromotionSourceRecord, PublishedProvenance
from app.domain.requirements import Requirement
from app.main import create_app

PATH = "/api/v1/eligibility/check"
DAY = date(2026, 10, 8)
STAMP = datetime(2026, 10, 1, tzinfo=UTC)
BODY = {
    "brand": " Maker ",
    "model": " Model-1 ",
    "retailer": " Shop ",
    "purchase_date": "2026-10-01",
}
IDENTITY = ResolvedPurchaseIdentity(*(UUID(int=i) for i in (1, 2, 3)))


def offer():
    return CheckPurchasePromotionResult(
        UUID(int=4),
        UUID(int=5),
        "Offer",
        None,
        PromotionStatus.ACTIVE,
        classify_eligibility(
            (RuleEvaluation(RuleKind.PRODUCT, RuleStatus.SATISFIED, RuleReasonCode.PRODUCT_MATCH),),
            ClaimWindowStatus.OPEN,
        ),
        ClaimWindowEvaluation(ClaimWindowStatus.OPEN, date(2026, 10, 1), date(2026, 10, 31)),
        (
            CheckPurchaseBenefit(
                UUID(int=6), Benefit("cashback", "Cashback"), Decimal("12.50"), None
            ),
            CheckPurchaseBenefit(UUID(int=7), Benefit("free_gift", "Gift"), None, None),
            CheckPurchaseBenefit(UUID(int=8), Benefit("extended_warranty", "Warranty"), None, None),
        ),
        (Requirement("receipt", None),),
        PublishedProvenance(
            "https://example.org/offer", "web_page", STAMP, STAMP, "https://example.org/claim"
        ),
        (
            PromotionSourceRecord(
                UUID(int=9), "supporting", "https://example.org/terms", "pdf", STAMP, None
            ),
        ),
        ("The claim window is open.",),
    )


@pytest.fixture
def harness(monkeypatch):
    app = create_app(
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg://user:password@localhost/benefits",
            APP_ENV="test",
        )
    )
    app.dependency_overrides[api.uk_evaluation_date] = lambda: DAY
    state = {
        "entered": 0,
        "closed": 0,
        "calls": [],
        "result": CheckPurchaseResult(DAY, IDENTITY, (offer(),)),
    }
    resolver, repository = object(), object()

    @contextmanager
    def snapshot(factory):
        assert factory is app.state.session_factory
        state["entered"] += 1
        try:
            yield resolver, repository
        finally:
            state["closed"] += 1

    def check(request, **kwargs):
        state["calls"].append((request, kwargs))
        assert kwargs == {
            "evaluation_date": DAY,
            "identity_resolver": resolver,
            "promotion_repository": repository,
        }
        if "error" in state:
            raise state["error"]
        return state["result"]

    monkeypatch.setattr(api, "purchase_check_snapshot", snapshot)
    monkeypatch.setattr(api, "check_purchase", check)
    with TestClient(app) as client:
        yield client, state


@pytest.mark.parametrize("price", [None, "0", "0.00", "12.50", "999999999999.99"])
def test_strict_request_mapping_and_complete_response(harness, price):
    client, state = harness
    response = client.post(PATH, json={**BODY, "purchase_price": price})
    assert response.status_code == 200
    request, _ = state["calls"][0]
    assert (request.brand, request.model, request.retailer) == (
        BODY["brand"],
        BODY["model"],
        BODY["retailer"],
    )
    assert request.purchase_date == date(2026, 10, 1)
    assert request.purchase_price == (Decimal(price) if price is not None else None)
    assert (
        request.purchase_price is None
        or request.purchase_price.as_tuple() == Decimal(price).as_tuple()
    )
    assert state["entered"] == state["closed"] == len(state["calls"]) == 1
    data = response.json()
    assert data["outcome"] == "resolved" and data["evaluation_date"] == DAY.isoformat()
    result = data["promotions"][0]
    assert result["benefits"][0]["cashback_reward_gbp"] == "12.50"
    assert [x["cashback_reward_gbp"] for x in result["benefits"][1:]] == [None, None]
    assert result["sources"][0]["verified_at"] is None
    assert result["provenance"]["retrieved_at"] == "2026-10-01T00:00:00Z"
    assert result["claim_window"] == {
        "status": "open",
        "opens_on": "2026-10-01",
        "deadline_on": "2026-10-31",
    }
    assert result["eligibility"]["rule_evaluations"] == [
        {"kind": "product", "status": "satisfied", "reason_code": "product_match"}
    ]
    assert result["requirements"] == [{"requirement_type": "receipt", "description": None}]
    UUID(response.headers["x-request-id"])


@pytest.mark.parametrize(
    "field,value",
    [
        ("purchase_price", value)
        for value in (
            0,
            12.5,
            True,
            "-1",
            "NaN",
            "Infinity",
            "1e2",
            "1,000",
            "£1",
            "1.001",
            "1000000000000",
            "01",
            "1\n",
        )
    ]
    + [
        ("purchase_date", value)
        for value in (
            True,
            20261001,
            "2026-10-01T00:00:00Z",
            "2026-02-30",
            "01/10/2026",
            "2026-1-1",
            None,
        )
    ]
    + [
        (field, value)
        for field in ("brand", "model", "retailer")
        for value in ("", "   ", "bad\x00", "x" * 256, "ß" * 128, True, 123, None)
    ]
    + [("evaluation_date", "2026-10-08"), ("currency", "GBP")],
)
def test_invalid_purchase_never_starts_snapshot(harness, field, value):
    client, state = harness
    response = client.post(PATH, json={**BODY, field: value})
    assert response.status_code == 422
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["code"] == "invalid_purchase_request"
    assert state["entered"] == 0 and not state["calls"]
    assert "input" not in response.json()


@pytest.mark.parametrize("body", [[], None, "text", {}, [BODY]])
def test_non_object_or_missing_fields(harness, body):
    client, state = harness
    assert (
        client.post(
            PATH,
            content=json.dumps(body),
            headers={"Content-Type": "application/json"},
        ).status_code
        == 422
    )
    assert state["entered"] == 0


@pytest.mark.parametrize(
    "body,content_type,status",
    [
        (b"{", "application/json", 422),
        (b"\xff", "application/json", 422),
        (b"[" * 2000 + b"]" * 2000, "application/json", 422),
        (b"{}", "text/plain", 415),
        (b"x" * 8193, "application/json", 413),
    ],
)
def test_boundary_failures(harness, body, content_type, status):
    client, state = harness
    response = client.post(PATH, content=body, headers={"Content-Type": content_type})
    assert response.status_code == status
    assert response.headers["content-type"] == "application/problem+json"
    assert state["entered"] == 0


def test_json_integer_digit_limit_is_safe_422(harness):
    client, state = harness
    body = (
        b'{"brand":"Maker","model":"Model-1","retailer":"Shop",'
        b'"purchase_date":"2026-10-01","purchase_price":' + b"1" * 5000 + b"}"
    )

    response = client.post(PATH, content=body, headers={"Content-Type": "application/json"})

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_purchase_request"
    assert state["entered"] == 0 and not state["calls"]


def test_chunked_body_without_content_length_is_bounded(harness):
    client, state = harness
    response = client.post(
        PATH, content=iter([b"x" * 4096, b"x" * 4097]), headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 413 and state["entered"] == 0


@pytest.mark.parametrize("status", [MatchStatus.NOT_FOUND, MatchStatus.AMBIGUOUS])
def test_unresolved_identity(harness, status):
    client, state = harness
    ids = (UUID(int=3), UUID(int=4)) if status == MatchStatus.AMBIGUOUS else ()
    state["result"] = UnresolvedPurchaseIdentity("model", status, ids)
    data = client.post(PATH, json=BODY).json()
    assert data == {
        "outcome": "unresolved_identity",
        "evaluation_date": DAY.isoformat(),
        "unresolved_identity": {
            "field": "model",
            "status": status.value,
            "candidate_ids": list(map(str, ids)),
        },
        "explanation": [state["result"].explanation],
    }


def test_no_match_and_missing_price(harness):
    client, state = harness
    state["result"] = CheckPurchaseResult(
        DAY,
        IDENTITY,
        (),
        NoMatchReason.NO_MATCHING_PUBLISHED_PROMOTIONS,
        ("No matching published promotion was found for this purchase.",),
    )
    data = client.post(PATH, json=BODY).json()
    assert (
        data["promotions"] == [] and data["no_match_reason"] == "no_matching_published_promotions"
    )
    assert state["calls"][0][0].purchase_price is None


@pytest.mark.parametrize("classification", list(EligibilityClassification))
def test_classifications_and_order_preserved(harness, classification):
    client, state = harness
    first = offer()
    first = replace(first, eligibility=replace(first.eligibility, classification=classification))
    second = replace(
        first,
        promotion_variant_id=UUID(int=2),
        claim_window=None,
        eligibility=replace(first.eligibility, claim_window_status=None),
        benefits=(
            CheckPurchaseBenefit(
                UUID(int=7),
                Benefit("cashback", "Percent"),
                None,
                RewardUnavailableReason.PURCHASE_PRICE_REQUIRED,
            ),
        ),
    )
    state["result"] = CheckPurchaseResult(DAY, IDENTITY, (first, second))
    data = client.post(PATH, json=BODY).json()["promotions"]
    assert [x["promotion_variant_id"] for x in data] == [str(UUID(int=5)), str(UUID(int=2))]
    assert data[0]["eligibility"]["classification"] == classification.value
    assert data[1]["claim_window"] is None
    assert data[1]["eligibility"]["claim_window_status"] is None
    assert (
        data[1]["benefits"][0]["reward_unavailable_reason"] == "purchase_price_required_for_reward"
    )


@pytest.mark.parametrize(
    "error,status,code",
    [
        (PublishedPromotionDataError(), 500, "published_data_invalid"),
        (IdentityPersistenceError("private"), 503, "eligibility_unavailable"),
        (PromotionPersistenceError("private"), 503, "eligibility_unavailable"),
        (RuntimeError("private"), 500, "internal_server_error"),
    ],
)
def test_safe_failure_and_snapshot_closure(harness, error, status, code):
    client, state = harness
    state["error"] = error
    response = client.post(PATH, json=BODY)
    assert response.status_code == status and response.json()["code"] == code
    assert "private" not in response.text
    assert state["closed"] == 1


def test_serializer_failure_closes_snapshot(harness, monkeypatch):
    client, state = harness

    def fail(*args):
        raise RuntimeError("private serializer")

    monkeypatch.setattr(api, "map_result", fail)
    assert client.post(PATH, json=BODY).json()["code"] == "internal_server_error"
    assert state["closed"] == 1


def test_uk_clock_uses_london_dst_date(monkeypatch):
    class Clock:
        @staticmethod
        def now(zone):
            assert zone.key == "Europe/London"
            return datetime(2026, 7, 1, 23, 30, tzinfo=UTC).astimezone(zone)

    monkeypatch.setattr(api, "datetime", Clock)
    assert api.uk_evaluation_date() == date(2026, 7, 2)


def test_openapi_contract(harness):
    client, _ = harness
    schema = client.get("/openapi.json").json()
    endpoint = schema["paths"][PATH]["post"]
    assert set(endpoint["responses"]) == {"200", "413", "415", "422", "429", "500", "503"}
    result = endpoint["responses"]["200"]["content"]["application/json"]["schema"]
    assert result["discriminator"]["propertyName"] == "outcome" and len(result["oneOf"]) == 2
    for response_model in ("ResolvedResponse", "UnresolvedResponse"):
        assert "outcome" in schema["components"]["schemas"][response_model]["required"]
    assert schema["components"]["schemas"]["PurchaseRequest"]["additionalProperties"] is False
    assert schema["components"]["schemas"]["EligibilityClassification"]["enum"] == [
        x.value for x in EligibilityClassification
    ]
    from app.api.schemas.eligibility import PurchaseRequest

    PurchaseRequest.model_validate(schema["components"]["schemas"]["PurchaseRequest"]["example"])


def test_domain_constructor_validation_is_safe_422(harness, monkeypatch):
    client, state = harness

    def reject(*args):
        raise ValueError("private raw domain input")

    monkeypatch.setattr(api, "CheckPurchaseRequest", reject)
    response = client.post(PATH, json=BODY)
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_purchase_request"
    assert "private" not in response.text
    assert state["entered"] == 0


def test_openapi_response_examples_validate(harness):
    from pydantic import TypeAdapter

    from app.api.schemas.eligibility import CheckResponse

    client, _ = harness
    examples = client.get("/openapi.json").json()["paths"][PATH]["post"]["responses"]["200"][
        "content"
    ]["application/json"]["examples"]
    for example in examples.values():
        TypeAdapter(CheckResponse).validate_python(example["value"])
