from datetime import date, timedelta
from decimal import Decimal
from functools import partial

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from app.api.eligibility import uk_evaluation_date
from app.application.promotions import PromotionPublicationError, change_promotion_status
from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.application.purchase_check_details import CheckPurchaseResult, NoMatchReason
from app.core.config import Settings
from app.db.models import Manufacturer, Product, Promotion, Retailer, Source
from app.db.repositories.promotions import promotion_transaction, purchase_check_snapshot
from app.domain.promotion_lifecycle import PromotionStatus as S
from app.main import create_app
from tests.integration.test_promotion_lifecycle import snapshot, transaction
from tests.samsung_reference import construct_reference, finish_reference, reference_manifest

pytestmark = pytest.mark.integration


@pytest.fixture
def reference(postgres_engine, migrated_test_database):
    factory = sessionmaker(postgres_engine)
    with factory.begin() as session:
        promotion = construct_reference(session)
        identity = promotion.id
        maker_id = promotion.manufacturer_id
        product_id = promotion.variants[0].product_links[0].product_id
        retailer_id = promotion.variants[0].retailer_id
        sources = [link.source_id for link in promotion.source_links]
        # Fake identities are intentionally separate from official campaign facts.
        other_shop = Retailer(name="Excluded test retailer", slug="excluded-test-retailer")
        other_product = Product(
            manufacturer_id=maker_id,
            name="Unlinked test model",
            slug="unlinked-test-model",
            model_number="TEST-NOT-SM-R640",
        )
        session.add_all([other_shop, other_product])
        session.flush()
        other_shop_id, other_product_id = other_shop.id, other_product.id
    try:
        finish_reference(partial(promotion_transaction, factory), identity)
        yield factory, identity
    finally:
        with factory.begin() as session:
            session.execute(delete(Promotion).where(Promotion.id == identity))
            session.execute(delete(Source).where(Source.id.in_(sources)))
            session.execute(delete(Product).where(Product.id.in_([product_id, other_product_id])))
            session.execute(delete(Retailer).where(Retailer.id.in_([retailer_id, other_shop_id])))
            session.execute(delete(Manufacturer).where(Manufacturer.id == maker_id))


def check(factory, purchase, evaluation, model="SM-R640", retailer="Samsung.com"):
    with purchase_check_snapshot(factory) as (resolver, repository):
        return check_purchase(
            CheckPurchaseRequest("Samsung", model, retailer, purchase),
            evaluation_date=evaluation,
            identity_resolver=resolver,
            promotion_repository=repository,
        )


@pytest.mark.parametrize(
    "purchase,evaluation,classification",
    [
        ("2026-06-03", "2026-06-03", "ELIGIBLE"),
        ("2026-06-03", "2026-07-02", "ELIGIBLE"),
        ("2026-06-03", "2026-07-03", "EXPIRED"),
        ("2026-06-23", "2026-06-23", "ELIGIBLE"),
        ("2026-06-23", "2026-07-22", "ELIGIBLE"),
        ("2026-06-23", "2026-07-23", "EXPIRED"),
        ("2026-06-23", "2026-10-09", "EXPIRED"),
    ],
)
def test_real_published_snapshot_boundaries(reference, purchase, evaluation, classification):
    factory, identity = reference
    f = reference_manifest()
    purchase = date.fromisoformat(purchase)
    result = check(factory, purchase, date.fromisoformat(evaluation))
    assert isinstance(result, CheckPurchaseResult) and result.no_match_reason is None
    assert len(result.promotions) == 1
    offer = result.promotions[0]
    assert offer.promotion_id == identity and offer.promotion_status == S.EXPIRED
    assert offer.eligibility.classification == classification
    assert [r.code for r in offer.eligibility.reasons] == [
        "all_configured_rules_satisfied",
        "claim_window_open" if classification == "ELIGIBLE" else "claim_window_expired",
    ]
    assert offer.claim_window.opens_on == purchase
    assert offer.claim_window.deadline_on == purchase + timedelta(days=29)
    assert len(offer.benefits) == 1
    assert offer.benefits[0].cashback_reward_gbp == Decimal("50.00")
    assert offer.benefits[0].reward_unavailable_reason is None
    assert "does not guarantee" in offer.benefits[0].benefit.description
    assert {r.requirement_type for r in offer.requirements} == {"receipt", "serial_number"}
    assert any("where requested" in r.description for r in offer.requirements)
    assert offer.provenance.official_source_url == f["official_terms_url"]
    assert offer.provenance.claim_url == f["claim_url"]
    assert {s.role for s in offer.sources} == {"primary", "claim", "supporting"}
    assert {s.url for s in offer.sources} == {
        f[k] for k in ("official_terms_url", "claim_url", "samsung_newsroom_url")
    }
    assert all(s.retrieved_at.tzinfo and s.verified_at >= s.retrieved_at for s in offer.sources)
    assert offer.explanation == (
        "The recorded eligibility rules match this purchase.",
        "The claim window is open."
        if classification == "ELIGIBLE"
        else "The claim deadline has passed.",
    )


@pytest.mark.parametrize(
    "purchase,evaluation,model,retailer",
    [
        ("2026-06-02", "2026-06-03", "SM-R640", "Samsung.com"),
        ("2026-06-24", "2026-06-24", "SM-R640", "Samsung.com"),
        ("2026-06-15", "2026-06-15", "SM-R640", "Excluded test retailer"),
        ("2026-06-15", "2026-06-15", "TEST-NOT-SM-R640", "Samsung.com"),
    ],
)
def test_resolved_exclusions_are_no_match(reference, purchase, evaluation, model, retailer):
    result = check(
        reference[0], date.fromisoformat(purchase), date.fromisoformat(evaluation), model, retailer
    )
    assert isinstance(result, CheckPurchaseResult)
    assert result.promotions == ()
    assert result.no_match_reason == NoMatchReason.NO_MATCHING_PUBLISHED_PROMOTIONS


@pytest.mark.parametrize("resume", [S.REVIEW, S.ACTIVE, S.EXPIRED])
def test_publication_resume_and_replay_preserve_all_reference_data(db_session, resume):
    with db_session.begin_nested():
        promotion = construct_reference(db_session)
    operation = partial(transaction, db_session)
    if resume != S.REVIEW:
        change_promotion_status(operation, promotion.id, S.ACTIVE)
    if resume == S.EXPIRED:
        change_promotion_status(operation, promotion.id, S.EXPIRED)
    before = snapshot(db_session)
    assert construct_reference(db_session).id == promotion.id
    finish_reference(operation, promotion.id)
    db_session.expire_all()
    assert db_session.get(Promotion, promotion.id).status == S.EXPIRED
    after = snapshot(db_session)
    assert all(before[t] == after[t] for t in before.keys() - {"promotions"})
    assert construct_reference(db_session).id == promotion.id
    finish_reference(operation, promotion.id)
    assert snapshot(db_session) == after


@pytest.mark.parametrize("role", ["primary", "claim", "manufacturer"])
def test_invalid_review_graph_cannot_publish(db_session, role):
    promotion = construct_reference(db_session)
    if role == "manufacturer":
        other = Manufacturer(name="Other test maker", slug="other-test-maker")
        product = Product(manufacturer=other, name="Wrong maker model", slug="wrong-maker-model")
        from app.db.models import PromotionVariantProduct

        promotion.variants[0].product_links.append(PromotionVariantProduct(product=product))
        code = "product_manufacturer_mismatch"
    else:
        next(link.source for link in promotion.source_links if link.role == role).verified_at = None
        code = f"{role}_source_unverified"
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(PromotionPublicationError) as error:
        change_promotion_status(partial(transaction, db_session), promotion.id, S.ACTIVE)
    assert code in {issue.code for issue in error.value.report.issues}
    assert snapshot(db_session) == before
    assert db_session.get(Promotion, promotion.id).status == S.REVIEW


def test_conflicting_graph_fails_without_replacement(db_session):
    promotion = construct_reference(db_session)
    promotion.variants[0].benefits[0].reward.fixed_amount = Decimal("99.00")
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(ValueError, match="Conflicting"):
        construct_reference(db_session)
    assert snapshot(db_session) == before


def test_atomic_construction_failure_rolls_back_and_retry_succeeds(db_session, monkeypatch):
    from tests import samsung_reference as helper

    before = snapshot(db_session)
    original = helper.validate_candidate_promotion

    def fail(candidate):
        raise ValueError("simulated candidate validation failure")

    monkeypatch.setattr(helper, "validate_candidate_promotion", fail)
    with pytest.raises(ValueError, match="simulated"), db_session.begin_nested():
        construct_reference(db_session)
    assert snapshot(db_session) == before
    monkeypatch.setattr(helper, "validate_candidate_promotion", original)
    with db_session.begin_nested():
        promotion = construct_reference(db_session)
    finish_reference(partial(transaction, db_session), promotion.id)
    db_session.expire_all()
    assert db_session.get(Promotion, promotion.id).status == S.EXPIRED


def test_http_existing_route_historical_and_no_match(reference, postgres_engine):
    app = create_app(
        Settings(_env_file=None, APP_ENV="test", DATABASE_URL="postgresql+psycopg://unused/unused"),
        engine_factory=lambda _: postgres_engine,
    )
    app.dependency_overrides[uk_evaluation_date] = lambda: date(2026, 7, 22)
    with TestClient(app) as client:
        body = {
            "brand": "Samsung",
            "model": "SM-R640",
            "retailer": "Samsung.com",
            "purchase_date": "2026-06-23",
        }
        response = client.post("/api/v1/eligibility/check", json=body)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        offer = response.json()["promotions"][0]
        assert offer["promotion_status"] == "expired"
        assert offer["eligibility"]["classification"] == "ELIGIBLE"
        assert offer["benefits"][0]["cashback_reward_gbp"] == "50.00"
        response = client.post(
            "/api/v1/eligibility/check", json={**body, "retailer": "Excluded test retailer"}
        )
        assert response.status_code == 200
        assert response.json()["promotions"] == []
        assert response.json()["no_match_reason"] == "no_matching_published_promotions"


def test_snapshot_reproducible_read_only_without_http(reference, postgres_engine, monkeypatch):
    import httpx
    from sqlalchemy import event

    def forbidden_http(*args, **kwargs):
        raise AssertionError("Reference purchase checks must not retrieve remote evidence")

    monkeypatch.setattr(httpx.Client, "send", forbidden_http)
    statements = []

    def record(connection, cursor, statement, *args):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(postgres_engine, "before_cursor_execute", record)
    try:
        first = check(reference[0], date(2026, 6, 23), date(2026, 7, 22))
        assert check(reference[0], date(2026, 6, 23), date(2026, 7, 22)) == first
        assert not {"INSERT", "UPDATE", "DELETE"}.intersection(statements)
    finally:
        event.remove(postgres_engine, "before_cursor_execute", record)


def test_canonical_aliases_reused_without_duplicate_identities(db_session):
    from app.db.models import ManufacturerAlias, ProductModelAlias, RetailerAlias

    maker = Manufacturer(name="Samsung Electronics", slug="samsung-electronics")
    shop = Retailer(name="Samsung online UK", slug="samsung-online-uk")
    product = Product(
        manufacturer=maker, name="Galaxy Buds4 Pro", slug="buds4-pro", model_number="SM-R640"
    )
    db_session.add_all([maker, shop, product])
    db_session.flush()
    db_session.add_all(
        [
            ManufacturerAlias(manufacturer_id=maker.id, alias="Samsung"),
            RetailerAlias(retailer_id=shop.id, alias="Samsung.com"),
            ProductModelAlias(product_id=product.id, alias="SM-R640"),
        ]
    )
    db_session.flush()
    promotion = construct_reference(db_session)
    assert promotion.manufacturer_id == maker.id
    assert promotion.variants[0].retailer_id == shop.id
    assert promotion.variants[0].product_links[0].product_id == product.id
    from sqlalchemy import func

    assert db_session.scalar(select(func.count()).select_from(Manufacturer)) == 1
    assert db_session.scalar(select(func.count()).select_from(Product)) == 1
    assert db_session.scalar(select(func.count()).select_from(Retailer)) == 1


@pytest.mark.parametrize("case", ["ambiguous", "wrong_name"])
def test_ambiguous_or_mislabelled_product_identity_is_rejected(db_session, case):
    maker = Manufacturer(name="Samsung", slug="samsung")
    shop = Retailer(name="Samsung.com", slug="samsung-com")
    products = [
        Product(
            manufacturer=maker,
            name="Different Buds model" if case == "wrong_name" else "Galaxy Buds4 Pro",
            slug="existing-buds",
            model_number="SM-R640",
        )
    ]
    if case == "ambiguous":
        products.append(
            Product(manufacturer=maker, name="Another", slug="another", model_number="SM-R640")
        )
    db_session.add_all([maker, shop, *products])
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(ValueError, match="identity"), db_session.begin_nested():
        construct_reference(db_session)
    assert snapshot(db_session) == before
