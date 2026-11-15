from contextlib import contextmanager

import pytest
from jsonschema import validate
from sqlalchemy import delete, event, select, text, update
from sqlalchemy.orm import Session

from app.api import promotions as api
from app.db.models import (
    Manufacturer,
    Product,
    Promotion,
    PromotionSource,
    PromotionVariant,
    PromotionVariantProduct,
)
from tests.integration.test_check_purchase import published_graph as published_graph
from tests.integration.test_eligibility_api import PATH as CHECK_PATH
from tests.integration.test_eligibility_api import body
from tests.integration.test_eligibility_api import http_client as http_client

pytestmark = pytest.mark.integration


def path(maker, promotion):
    return f"/api/v1/promotions/{maker}/{promotion}"


def identities(engine, promotion_id):
    with engine.connect() as connection:
        return connection.execute(
            select(Manufacturer.slug, Promotion.slug)
            .join(Promotion)
            .where(Promotion.id == promotion_id)
        ).one()


def test_public_read_is_coherent_and_deterministic(
    http_client, postgres_engine, published_graph, monkeypatch
):
    _, promotions, variants, product = published_graph
    maker, slug = identities(postgres_engine, promotions[0])
    original = api.purchase_check_snapshot
    statements, rollbacks = [], []

    @contextmanager
    def snapshot(*args, **kwargs):
        with original(*args, **kwargs) as pair:
            session = pair[1].session
            assert session.scalar(text("SHOW transaction_read_only")) == "on"
            assert session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            yield pair

    def record(_conn, _cursor, statement, *_args):
        statements.append(statement.strip().split()[0].upper())

    def rollback(_conn):
        rollbacks.append(True)

    monkeypatch.setattr(api, "purchase_check_snapshot", snapshot)
    event.listen(postgres_engine, "before_cursor_execute", record)
    event.listen(postgres_engine, "rollback", rollback)
    try:
        response = http_client.get(path(maker, slug))
        assert response.status_code == 200
        data = response.json()
        assert data == http_client.get(path(maker, slug)).json()
        assert data["public_slug"] == f"{maker}--{slug}"
        assert [item["promotion_variant_id"] for item in data["variants"]] == list(
            map(str, variants[:2])
        )
        assert [item["products"][0]["id"] for item in data["variants"]] == [str(product)] * 2
        assert data["variants"][0]["retailer"]["name"].startswith("Shop ")
        assert data["variants"][1]["retailer"] is None
        assert data["claim_window"] == {
            "kind": "fixed",
            "opens_on": "2024-02-29",
            "deadline_on": "2024-03-30",
            "minimum_days_after_purchase": None,
        }
        assert [item["role"] for item in data["sources"]] == ["claim", "primary", "supporting"]
        assert len(data["variants"][0]["requirements"]) == 3
        spec = http_client.get("/openapi.json").json()
        validate(
            data,
            {"$ref": "#/components/schemas/PromotionDetails", "components": spec["components"]},
        )
        assert not ({"INSERT", "UPDATE", "DELETE", "COMMIT"} & set(statements))
        assert len(rollbacks) == 2
        assert postgres_engine.pool.checkedout() == 0
    finally:
        event.remove(postgres_engine, "before_cursor_execute", record)
        event.remove(postgres_engine, "rollback", rollback)


def test_same_slug_lifecycle_claim_windows_and_corrupt_relationships(
    http_client, postgres_engine, published_graph
):
    request, promotions, variants, _ = published_graph
    maker, slug = identities(postgres_engine, promotions[0])
    _, expired_slug = identities(postgres_engine, promotions[1])
    other_slug = maker + "-other"
    with Session(postgres_engine) as session, session.begin():
        copy_from = session.get(Promotion, promotions[0])
        other_maker = Manufacturer(name="Second Maker", slug=other_slug)
        other_product = Product(
            manufacturer=other_maker, name="Other product", slug="other-product"
        )
        other = Promotion(manufacturer=other_maker, name="Second Offer", slug=slug, status="active")
        other.source_links = [
            PromotionSource(source_id=link.source_id, role=link.role)
            for link in copy_from.source_links
        ]
        variant = PromotionVariant(promotion=other, code="other")
        session.add_all([other, other_product, variant])
        session.flush()
        from app.db.models import Benefit

        session.add_all(
            [
                Benefit(promotion_variant_id=variant.id, benefit_type="free_gift", name="Gift"),
                PromotionVariantProduct(
                    promotion_variant_id=variant.id, product_id=other_product.id
                ),
            ]
        )
        copy_from.claim_min_wait_days = 10
        other_ids = (other.id, other_product.id, other_maker.id)

    try:
        check = http_client.post(CHECK_PATH, json=body(request)).json()
        assert (
            next(
                item for item in check["promotions"] if item["promotion_id"] == str(promotions[0])
            )["public_slug"]
            == f"{maker}--{slug}"
        )
        fixed = http_client.get(path(maker, slug)).json()
        assert fixed["claim_window"]["minimum_days_after_purchase"] == 10
        alternate = http_client.get(path(other_slug, slug)).json()
        assert alternate["name"] == "Second Offer"
        assert alternate["public_slug"] == f"{other_slug}--{slug}"
        assert alternate["claim_window"] is None
        expired = http_client.get(path(maker, expired_slug)).json()
        assert expired["status"] == "expired"
        assert expired["claim_window"] == {
            "kind": "relative",
            "opens_after_purchase_days": 0,
            "deadline_after_purchase_days": 30,
        }
        reward = next(
            item["reward"]
            for item in expired["variants"][0]["benefits"]
            if item["benefit_type"] == "cashback"
        )
        assert reward["kind"] == "product_specific"
        assert reward["values"][0]["amount_gbp"] == "42"
        for missing in [
            "missing",
            *(identities(postgres_engine, item)[1] for item in promotions[2:]),
        ]:
            assert http_client.get(path(maker, missing)).status_code == 404
        with postgres_engine.begin() as connection:
            connection.execute(
                update(Promotion).where(Promotion.id == other_ids[0]).values(status="discovered")
            )
            connection.execute(
                delete(PromotionVariantProduct).where(
                    PromotionVariantProduct.promotion_variant_id == variants[0]
                )
            )
        assert http_client.get(path(other_slug, slug)).status_code == 404
        response = http_client.get(path(maker, slug))
        assert response.status_code == 500 and "variants" not in response.json()
        with postgres_engine.begin() as connection:
            connection.execute(
                delete(PromotionSource).where(
                    PromotionSource.promotion_id == promotions[1], PromotionSource.role == "claim"
                )
            )
        assert http_client.get(path(maker, expired_slug)).status_code == 500
        assert postgres_engine.pool.checkedout() == 0
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(delete(Promotion).where(Promotion.id == other_ids[0]))
            connection.execute(delete(Product).where(Product.id == other_ids[1]))
            connection.execute(delete(Manufacturer).where(Manufacturer.id == other_ids[2]))
