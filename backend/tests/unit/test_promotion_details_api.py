from contextlib import contextmanager
from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.api import promotions as api
from app.application.promotion_details import (
    PublicIdentity,
    PublicProduct,
    PublicPromotion,
    PublicVariant,
)
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check_details import (
    PublishedBenefit,
    PublishedPromotionDataError,
    PublishedPromotionDetails,
)
from app.core.config import Settings
from app.domain.benefits import Benefit
from app.domain.promotion_lifecycle import PromotionStatus
from app.domain.promotion_provenance import PromotionSourceRecord
from app.main import create_app

PATH = "/api/v1/promotions/maker/same-offer"


@pytest.fixture
def client(monkeypatch):
    app = create_app(
        Settings(_env_file=None, APP_ENV="test", DATABASE_URL="postgresql+psycopg://unused/unused")
    )
    state = {"calls": [], "value": None}

    def load(*slugs):
        state["calls"].append(slugs)
        if isinstance(state["value"], BaseException):
            raise state["value"]
        return state["value"]

    @contextmanager
    def snapshot(*_args, **_kwargs):
        yield None, SimpleNamespace(load_public_promotion=load)

    monkeypatch.setattr(api, "purchase_check_snapshot", snapshot)
    with TestClient(app) as transport:
        yield transport, state


def test_public_response(client):
    transport, state = client
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    product = PublicProduct(UUID(int=3), "Series One", "M-1")
    maker = PublicIdentity(UUID(int=5), "Maker")
    details = PublishedPromotionDetails(
        UUID(int=1),
        UUID(int=2),
        "Offer",
        None,
        PromotionStatus.ACTIVE,
        maker.id,
        None,
        frozenset({product.id}),
        None,
        None,
        date(2026, 1, 2),
        date(2026, 1, 31),
        benefits=(PublishedBenefit(UUID(int=4), Benefit("cashback", "Cashback"), None),),
        sources=tuple(
            PromotionSourceRecord(
                UUID(int=index), role, f"https://example.com/{role}", "web_page", stamp, verified
            )
            for index, role, verified in [
                (6, "primary", stamp),
                (7, "claim", stamp),
                (8, "supporting", None),
            ]
        ),
        claim_min_wait_days=5,
    )
    state["value"] = PublicPromotion(
        maker, "maker", "same-offer", (PublicVariant(details, "all", (product,), None),)
    )
    response = transport.get(PATH)
    assert response.status_code == 200 and response.headers["Cache-Control"] == "no-store"
    assert response.headers["content-type"] == "application/json"
    assert response.json()["public_slug"] == "maker--same-offer"
    assert response.json()["variants"][0]["products"] == [
        {"id": str(product.id), "name": "Series One", "model_number": "M-1"}
    ]
    assert response.json()["claim_window"] == {
        "kind": "fixed",
        "opens_on": "2026-01-02",
        "deadline_on": "2026-01-31",
        "minimum_days_after_purchase": 5,
    }
    assert response.json()["sources"][-1]["verified_at"] is None


def test_openapi_documents_canonical_slug_parameters_and_error_statuses(client):
    transport, _ = client
    operation = transport.get("/openapi.json").json()["paths"][
        "/api/v1/promotions/{manufacturer_slug}/{promotion_slug}"
    ]["get"]
    parameters = {parameter["name"]: parameter["schema"] for parameter in operation["parameters"]}
    for name in ("manufacturer_slug", "promotion_slug"):
        assert parameters[name]["pattern"] == r"^[a-z0-9]+(-[a-z0-9]+)*$"
        assert parameters[name]["maxLength"] == 255
    assert {"200", "404", "500", "503"} <= set(operation["responses"])
    assert "422" not in operation["responses"]


def test_invalid_numeric_source_host_fails_closed(client):
    transport, state = client
    stamp = datetime(2026, 1, 1, tzinfo=UTC)
    source = PromotionSourceRecord(
        UUID(int=6), "primary", "https://999.999.999.999/offer", "web_page", stamp, stamp
    )
    details = PublishedPromotionDetails(
        UUID(int=1),
        UUID(int=2),
        "Offer",
        None,
        PromotionStatus.ACTIVE,
        UUID(int=5),
        None,
        frozenset({UUID(int=3)}),
        None,
        None,
        date(2026, 1, 2),
        date(2026, 1, 31),
        benefits=(PublishedBenefit(UUID(int=4), Benefit("cashback", "Cashback"), None),),
        sources=(
            source,
            PromotionSourceRecord(
                UUID(int=7), "claim", "https://example.com/claim", "web_page", stamp, stamp
            ),
        ),
    )
    maker = PublicIdentity(UUID(int=5), "Maker")
    product = PublicProduct(UUID(int=3), "Product", None)
    state["value"] = PublicPromotion(
        maker, "maker", "same-offer", (PublicVariant(details, "all", (product,), None),)
    )
    response = transport.get(PATH)
    assert response.status_code == 500
    assert response.json()["code"] == "published_data_invalid"
    assert "999.999" not in response.text


@pytest.mark.parametrize("component", ["Maker", "--maker", "a" * 256, "ma%6Ber", "a_b", "a--b"])
def test_malformed_key_is_hidden_before_repository_call(client, component):
    transport, state = client
    response = transport.get(f"/api/v1/promotions/{component}/same-offer")
    assert response.status_code == 404
    assert not state["calls"]


@pytest.mark.parametrize(
    ("failure", "status", "code"),
    [
        (None, 404, "promotion_not_found"),
        (PublishedPromotionDataError("secret projection"), 500, "published_data_invalid"),
        (PromotionPersistenceError("secret SQL"), 503, "promotions_unavailable"),
        (RuntimeError("secret runtime"), 500, "internal_server_error"),
    ],
)
def test_safe_problem(client, failure, status, code):
    transport, state = client
    state["value"] = failure
    response = transport.get(PATH)
    assert response.status_code == status
    assert response.headers["Content-Type"] == "application/problem+json"
    assert response.headers["Cache-Control"] == "no-store"
    assert response.json()["code"] == code
    assert response.json()["request_id"] == response.headers["X-Request-ID"]
    assert "secret" not in response.text
