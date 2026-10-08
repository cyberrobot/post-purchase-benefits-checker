from dataclasses import asdict
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, event

from app.api.eligibility import uk_evaluation_date
from app.core.config import Settings
from app.db.models import PromotionSource
from app.main import create_app
from tests.integration.test_check_purchase import DAY
from tests.integration.test_check_purchase import published_graph as published_graph

pytestmark = pytest.mark.integration
PATH = "/api/v1/eligibility/check"


@pytest.fixture
def http_client(postgres_engine, published_graph):
    app = create_app(
        Settings(_env_file=None, APP_ENV="test", DATABASE_URL="postgresql+psycopg://unused/unused"),
        engine_factory=lambda _: postgres_engine,
    )
    app.dependency_overrides[uk_evaluation_date] = lambda: DAY
    with TestClient(app) as client:
        yield client


def body(request, price=None):
    data = asdict(request)
    data["purchase_date"] = request.purchase_date.isoformat()
    data["purchase_price"] = str(price if price is not None else request.purchase_price)
    return data


def test_http_real_snapshot_complete_projection_and_no_writes(
    http_client, postgres_engine, published_graph
):
    request, _, variants, _ = published_graph
    statements, rollbacks = [], []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split()[0].upper())

    def rollback(connection):
        rollbacks.append(True)

    event.listen(postgres_engine, "before_cursor_execute", record)
    event.listen(postgres_engine, "rollback", rollback)
    try:
        response = http_client.post(PATH, json=body(request))
        assert response.status_code == 200
        data = response.json()
        assert data["evaluation_date"] == DAY.isoformat()
        assert len(data["promotions"]) == 3
        assert {x["promotion_variant_id"] for x in data["promotions"]} == set(
            map(str, variants[:3])
        )
        assert {x["promotion_status"] for x in data["promotions"]} == {"active", "expired"}
        for offer in data["promotions"]:
            assert offer["eligibility"]["classification"] == "ELIGIBLE"
            assert offer["claim_window"]["status"] == "open"
            assert (
                len(offer["benefits"]) == len(offer["requirements"]) == len(offer["sources"]) == 3
            )
            assert offer["provenance"]["claim_url"].endswith("/claim")
        assert {
            b["cashback_reward_gbp"]
            for p in data["promotions"]
            for b in p["benefits"]
            if b["cashback_reward_gbp"] is not None
        } == {"100.00", "20.00", "42.00"}
        assert http_client.post(PATH, json=body(request)).json() == data
        assert not ({"INSERT", "UPDATE", "DELETE", "COMMIT"} & set(statements))
        assert len(rollbacks) == 2
        assert postgres_engine.pool.checkedout() == 0
    finally:
        event.remove(postgres_engine, "before_cursor_execute", record)
        event.remove(postgres_engine, "rollback", rollback)


def test_http_zero_missing_price_unresolved_and_no_match(http_client, published_graph):
    request, _, _, _ = published_graph
    data = http_client.post(PATH, json=body(request, Decimal("0.00"))).json()
    amounts = [b["cashback_reward_gbp"] for p in data["promotions"] for b in p["benefits"]]
    assert "0.00" in amounts
    missing = body(request)
    missing.pop("purchase_price")
    data = http_client.post(PATH, json=missing).json()
    assert any(
        b["reward_unavailable_reason"] == "purchase_price_required_for_reward"
        for p in data["promotions"]
        for b in p["benefits"]
    )
    unknown = http_client.post(PATH, json={**body(request), "model": "unknown-model"})
    assert unknown.status_code == 200 and unknown.json()["outcome"] == "unresolved_identity"
    no_match = http_client.post(PATH, json={**body(request), "purchase_date": "2020-01-01"})
    assert no_match.status_code == 200 and no_match.json()["promotions"] == []
    assert no_match.json()["no_match_reason"] == "no_matching_published_promotions"


def test_http_invalid_published_data_never_partial_success(
    http_client, postgres_engine, published_graph
):
    request, promotions, _, _ = published_graph
    with postgres_engine.begin() as connection:
        connection.execute(
            delete(PromotionSource).where(
                PromotionSource.promotion_id == promotions[0], PromotionSource.role == "claim"
            )
        )
    response = http_client.post(PATH, json=body(request))
    assert response.status_code == 500
    assert response.json()["code"] == "published_data_invalid"
    assert "promotions" not in response.json()
    assert postgres_engine.pool.checkedout() == 0


def test_http_uses_read_only_repeatable_snapshot_during_concurrent_change(
    http_client, postgres_engine, published_graph, monkeypatch
):
    from contextlib import contextmanager

    from sqlalchemy import text, update

    from app.api import eligibility as api
    from app.db.models import Promotion

    request, promotions, _, _ = published_graph
    original_snapshot = api.purchase_check_snapshot

    @contextmanager
    def observed_snapshot(factory):
        with original_snapshot(factory) as (resolver, repository):
            assert (
                repository.session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            )
            assert repository.session.scalar(text("SHOW transaction_read_only")) == "on"
            original_candidates = repository.find_promotion_candidates

            def change_after_candidates(**kwargs):
                candidates = original_candidates(**kwargs)
                with postgres_engine.begin() as connection:
                    connection.execute(
                        update(Promotion)
                        .where(Promotion.id == promotions[0])
                        .values(name="Changed concurrently")
                    )
                return candidates

            repository.find_promotion_candidates = change_after_candidates
            yield resolver, repository

    monkeypatch.setattr(api, "purchase_check_snapshot", observed_snapshot)
    response = http_client.post(PATH, json=body(request))
    assert response.status_code == 200
    assert all(
        p["promotion_name"] == "Offer 0"
        for p in response.json()["promotions"]
        if p["promotion_id"] == str(promotions[0])
    )
    assert postgres_engine.pool.checkedout() == 0
