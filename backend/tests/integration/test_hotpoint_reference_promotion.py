from datetime import date, datetime
from decimal import Decimal
from functools import partial

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select, update
from sqlalchemy.orm import sessionmaker

from app.api.eligibility import uk_evaluation_date
from app.application.promotions import (
    PromotionPublicationError,
    change_promotion_status,
)
from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.application.purchase_check_details import CheckPurchaseResult
from app.core.config import Settings
from app.db.models import BenefitReward, Manufacturer, Product, Promotion, Retailer, Source
from app.db.repositories.promotions import (
    promotion_transaction,
    purchase_check_snapshot,
)
from app.domain.eligibility_result import EligibilityReasonCode
from app.domain.promotion_lifecycle import PromotionStatus
from app.main import create_app
from tests.hotpoint_reference import construct_reference, reference_manifest
from tests.integration.test_promotion_lifecycle import snapshot, transaction

pytestmark = [
    pytest.mark.integration,
    pytest.mark.filterwarnings("error::sqlalchemy.exc.SAWarning"),
]


@pytest.fixture(autouse=True)
def no_manufacturer_http(monkeypatch):
    """Guard external page retrieval while allowing existing Docker infrastructure."""
    from urllib.parse import urlsplit

    import httpx
    import requests

    original = requests.sessions.Session.request

    def guarded_request(session, method, url, *args, **kwargs):
        host = urlsplit(url).hostname or ""
        if host.endswith("hotpoint.co.uk") or host.endswith("wrenkitchens.com"):
            raise AssertionError("Reference tests must not fetch manufacturer/retailer pages")
        return original(session, method, url, *args, **kwargs)

    def forbidden_http(*args, **kwargs):
        raise AssertionError("Reference tests must not perform external HTTP retrieval")

    monkeypatch.setattr(requests.sessions.Session, "request", guarded_request)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden_http)


@pytest.fixture
def reference(postgres_engine, migrated_test_database):
    factory = sessionmaker(postgres_engine)
    with factory.begin() as session:
        owned_types = (Promotion, Source, Product, Retailer, Manufacturer)
        before = {kind: set(session.scalars(select(kind.id))) for kind in owned_types}
        promotion = construct_reference(session)
        promotion_id = promotion.id
        wrong_product = Product(
            manufacturer_id=promotion.manufacturer_id,
            name="Unlinked test model",
            slug="hotpoint-unlinked-test-model",
            model_number="TEST-NOT-H7IC16M6 UK",
        )
        wrong_retailer = Retailer(name="Excluded test retailer", slug="hotpoint-excluded-retailer")
        session.add_all([wrong_product, wrong_retailer])
        session.flush()
        owned = {kind: set(session.scalars(select(kind.id))) - before[kind] for kind in owned_types}
    try:
        yield factory, promotion_id
    finally:
        with factory.begin() as session:
            delete_owned_rows(session, owned)


def delete_owned_rows(session, owned):
    """Delete only fixture-owned graph/identity rows in FK-safe order."""
    for kind in (Promotion, Source, Product, Retailer, Manufacturer):
        if owned[kind]:
            session.execute(delete(kind).where(kind.id.in_(owned[kind])))


def test_constructor_replay_preserves_review_graph(db_session):
    first = construct_reference(db_session)
    first_id = first.id
    db_session.flush()
    second = construct_reference(db_session)
    assert second.id == first_id
    assert second.status == PromotionStatus.REVIEW


def test_constructor_replay_rejects_stale_identity_map_reward(db_session):
    promotion = construct_reference(db_session)
    db_session.flush()
    reward_id = promotion.variants[0].benefits[0].reward.benefit_id

    db_session.execute(
        update(BenefitReward)
        .where(BenefitReward.benefit_id == reward_id)
        .values(fixed_amount=Decimal("70.00")),
        execution_options={"synchronize_session": False},
    )

    with pytest.raises(ValueError, match="Conflicting existing verified reference"):
        construct_reference(db_session)


def test_historical_expired_promotion_replay_preserves_lifecycle_and_graph(db_session):
    promotion = construct_reference(db_session)
    operation = partial(transaction, db_session)
    change_promotion_status(operation, promotion.id, PromotionStatus.ACTIVE)
    change_promotion_status(operation, promotion.id, PromotionStatus.EXPIRED)
    before = _graph_ids(db_session)
    db_session.expire_all()
    replay = construct_reference(db_session)
    assert replay.id == promotion.id
    assert replay.status == PromotionStatus.EXPIRED
    assert _graph_ids(db_session) == before


@pytest.mark.parametrize(
    "purchase,evaluation,classification,opens",
    [
        ("2026-05-04", "2026-10-12", "NO_MATCH", None),
        ("2026-05-05", "2026-06-03", "CLAIM_NOT_YET_OPEN", "2026-06-04"),
        ("2026-05-05", "2026-06-04", "ELIGIBLE", "2026-06-04"),
        ("2026-05-05", "2026-10-12", "ELIGIBLE", "2026-06-04"),
        ("2026-06-12", "2026-07-12", "ELIGIBLE", "2026-07-12"),
        ("2026-06-12", "2026-12-04", "ELIGIBLE", "2026-07-12"),
        ("2026-06-12", "2026-12-05", "EXPIRED", "2026-07-12"),
        ("2026-06-13", "2026-10-12", "NO_MATCH", None),
    ],
)
def test_real_published_snapshot_boundaries(reference, purchase, evaluation, classification, opens):
    factory, identity = reference
    publish(factory, identity)
    with factory() as session:
        promotion = session.get(Promotion, identity)
        assert promotion.claim_start_date == date(2026, 6, 4)
        assert promotion.claim_end_date == date(2026, 12, 4)
        assert promotion.claim_start_offset_days is None
        assert promotion.claim_end_offset_days is None
        graph_before = snapshot(session)
    result = check(factory, date.fromisoformat(purchase), date.fromisoformat(evaluation))
    if classification == "NO_MATCH":
        assert isinstance(result, CheckPurchaseResult)
        assert result.promotions == ()
        assert result.no_match_reason == "no_matching_published_promotions"
        return
    assert isinstance(result, CheckPurchaseResult) and result.no_match_reason is None
    assert len(result.promotions) == 1
    offer = result.promotions[0]
    assert offer.promotion_id == identity
    assert offer.promotion_status == PromotionStatus.ACTIVE
    assert offer.eligibility.classification == classification
    assert offer.claim_window.opens_on == date.fromisoformat(opens)
    assert offer.claim_window.deadline_on == date(2026, 12, 4)
    assert offer.benefits[0].cashback_reward_gbp == Decimal("75.00")
    assert {r.requirement_type for r in offer.requirements} == {
        "receipt",
        "serial_number",
        "registration",
    }
    f = reference_manifest()
    assert offer.provenance.official_source_url == f["official_terms_url"]
    assert offer.provenance.claim_url == f["claim_url"]
    assert offer.provenance.source_type == "web_page"
    assert all(source.source_type == "web_page" for source in offer.sources)
    assert {s.role for s in offer.sources} == {"primary", "claim"}
    assert all(s.retrieved_at.tzinfo and s.verified_at >= s.retrieved_at for s in offer.sources)
    assert offer.explanation[0] == "The recorded eligibility rules match this purchase."
    expected_claim_reason = {
        "CLAIM_NOT_YET_OPEN": EligibilityReasonCode.CLAIM_WINDOW_NOT_YET_OPEN,
        "ELIGIBLE": EligibilityReasonCode.CLAIM_WINDOW_OPEN,
        "EXPIRED": EligibilityReasonCode.CLAIM_WINDOW_EXPIRED,
    }[classification]
    assert [reason.code for reason in offer.eligibility.reasons] == [
        EligibilityReasonCode.ALL_CONFIGURED_RULES_SATISFIED,
        expected_claim_reason,
    ]
    if classification == "CLAIM_NOT_YET_OPEN":
        assert "2026-06-04" in offer.explanation[1]
    elif classification == "EXPIRED":
        assert "deadline has passed" in offer.explanation[1].lower()
        with factory() as session:
            persisted = session.get(Promotion, identity)
            assert persisted.status == PromotionStatus.ACTIVE
            assert snapshot(session) == graph_before


def test_purchase_price_is_retained_as_exact_fixed_cashback_after_persistence(reference):
    factory, identity = reference
    publish(factory, identity)
    result = check(
        factory,
        date(2026, 6, 12),
        date(2026, 10, 12),
        price=Decimal("75.00"),
    )
    offer = result.promotions[0]
    assert offer.promotion_id == identity
    assert offer.benefits[0].cashback_reward_gbp == Decimal("75.00")


def test_verified_candidate_publishes_through_validation_gate_and_is_visible(reference):
    factory, promotion_id = reference
    with factory() as session:
        candidate = session.get(Promotion, promotion_id)
        assert candidate.status == PromotionStatus.REVIEW
        assert {link.role for link in candidate.source_links} == {"primary", "claim"}
        assert all(link.source.verified_at is not None for link in candidate.source_links)
        assert all(link.source.source_type == "web_page" for link in candidate.source_links)
        manifest = reference_manifest()
        assert {link.source.url for link in candidate.source_links} == {
            manifest["official_terms_url"],
            manifest["claim_url"],
        }
        assert {r.requirement_type for r in candidate.variants[0].requirements} == {
            "receipt",
            "serial_number",
            "registration",
        }
        assert candidate.variants[0].benefits[0].reward.fixed_amount == Decimal("75.00")
    invisible = check(factory, date(2026, 5, 5), date(2026, 10, 12))
    assert invisible.promotions == ()
    assert invisible.no_match_reason == "no_matching_published_promotions"
    publish(factory, promotion_id)
    with factory.begin() as session:
        replay = construct_reference(session)
        assert replay.id == promotion_id
        assert replay.status == PromotionStatus.ACTIVE
    with factory() as session:
        assert session.get(Promotion, promotion_id).status == PromotionStatus.ACTIVE
    assert check(factory, date(2026, 6, 1), date(2026, 10, 12)).promotions


@pytest.mark.parametrize("role", ["primary", "claim"])
def test_unverified_required_source_cannot_publish(db_session, role):
    promotion = construct_reference(db_session)
    source = next(link.source for link in promotion.source_links if link.role == role)
    source.verified_at = None
    db_session.flush()
    with pytest.raises(PromotionPublicationError) as error:
        change_promotion_status(
            partial(transaction, db_session), promotion.id, PromotionStatus.ACTIVE
        )
    assert f"{role}_source_unverified" in {issue.code for issue in error.value.report.issues}
    assert promotion.status == PromotionStatus.REVIEW


def test_candidate_replay_reuses_verified_sources(reference):
    factory, promotion_id = reference
    with factory.begin() as session:
        first = session.get(Promotion, promotion_id)
        first_source_ids = {link.source_id for link in first.source_links}
    with factory.begin() as session:
        replay = construct_reference(session)
        assert replay.id == promotion_id
        assert {link.source_id for link in replay.source_links} == first_source_ids
    with factory() as session:
        assert session.get(Promotion, promotion_id).status == PromotionStatus.REVIEW


def test_constructor_preflight_failure_rolls_back_savepoint_and_preserves_caller_state(
    db_session, monkeypatch
):
    from app.db.reference import hotpoint as helper

    marker = Retailer(name="Caller pending retailer", slug="caller-pending-retailer")
    db_session.add(marker)
    db_session.flush()
    before_ids = _graph_ids(db_session)

    def fail(_candidate):
        raise ValueError("simulated candidate preflight failure")

    monkeypatch.setattr(helper, "validate_candidate_promotion", fail)
    with pytest.raises(ValueError, match="simulated candidate preflight failure"):
        construct_reference(db_session)

    assert marker in db_session
    assert _graph_ids(db_session) == before_ids
    monkeypatch.undo()
    with db_session.begin_nested():
        promotion = construct_reference(db_session)
    assert promotion.status == PromotionStatus.REVIEW


def test_conflicting_existing_candidate_replay_preserves_existing_reward(db_session):
    promotion = construct_reference(db_session)
    reward = promotion.variants[0].benefits[0].reward
    values = reward.product_values
    db_session.flush()
    reward.fixed_amount = Decimal("99.00")
    db_session.flush()
    with pytest.raises(ValueError, match="Conflicting existing"):
        construct_reference(db_session)
    assert reward.fixed_amount == Decimal("99.00")
    assert values == []


def test_ambiguous_hotpoint_identity_rolls_back_candidate_graph(db_session):
    from app.db.models import ManufacturerAlias

    canonical = Manufacturer(name="Hotpoint", slug="hotpoint")
    other = Manufacturer(name="Hotpoint Alias Conflict", slug="hotpoint-alias-conflict")
    db_session.add_all([canonical, other])
    db_session.flush()
    db_session.add(ManufacturerAlias(manufacturer_id=other.id, alias="Hotpoint"))
    db_session.flush()
    before_manufacturers = set(db_session.scalars(select(Manufacturer.id)))
    before_promotions = set(db_session.scalars(select(Promotion.id)))

    with pytest.raises(ValueError, match="Ambiguous"):
        construct_reference(db_session)

    assert set(db_session.scalars(select(Manufacturer.id))) == before_manufacturers
    assert set(db_session.scalars(select(Promotion.id))) == before_promotions


def _graph_ids(session):
    from app.db.models import Benefit, BenefitReward, PromotionSource, PromotionVariant

    return {
        model.__tablename__: set(session.execute(select(*model.__table__.primary_key.columns)))
        for model in (
            Manufacturer,
            Retailer,
            Product,
            Promotion,
            PromotionVariant,
            Benefit,
            BenefitReward,
            Source,
        )
    } | {
        "promotion_sources": set(
            session.execute(select(PromotionSource.promotion_id, PromotionSource.source_id))
        )
    }


@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_pending_caller_state_is_not_flushed_or_rolled_back(db_session, pending):
    caller = Retailer(name="Unrelated caller retailer", slug="unrelated-caller-retailer")
    if pending != "new":
        db_session.add(caller)
        db_session.flush()
    before = _graph_ids(db_session)
    if pending == "new":
        db_session.add(caller)
    elif pending == "dirty":
        caller.name = "Changed caller retailer"
    else:
        db_session.delete(caller)
    with pytest.raises(ValueError, match="without pending changes"):
        construct_reference(db_session)
    assert caller in getattr(db_session, pending)
    with db_session.no_autoflush:
        assert _graph_ids(db_session) == before
    db_session.flush()


def test_canonical_aliases_reuse_existing_owned_product(db_session):
    from app.db.models import ManufacturerAlias, RetailerAlias

    maker = Manufacturer(name="Hotpoint UK", slug="hotpoint-uk")
    shop = Retailer(name="Wren UK", slug="wren-uk")
    product = Product(
        manufacturer=maker,
        name="Existing washer",
        slug="existing-washer",
        model_number="h7ic16m6 uk",
    )
    db_session.add_all([maker, shop, product])
    db_session.flush()
    db_session.add_all(
        [
            ManufacturerAlias(manufacturer_id=maker.id, alias="Hotpoint"),
            RetailerAlias(retailer_id=shop.id, alias="Wren"),
        ]
    )
    db_session.flush()
    before = _graph_ids(db_session)
    candidate = construct_reference(db_session)
    assert candidate.manufacturer_id == maker.id
    assert candidate.variants[0].retailer_id == shop.id
    assert candidate.variants[0].product_links[0].product_id == product.id
    after = _graph_ids(db_session)
    for table in ("manufacturers", "retailers", "products"):
        assert after[table] == before[table]


def test_exact_model_reuses_product_with_different_display_name(db_session):
    from app.db.models import ManufacturerAlias, RetailerAlias

    maker = Manufacturer(name="Hotpoint UK", slug="hotpoint-uk")
    shop = Retailer(name="Wren UK", slug="wren-uk")
    product = Product(
        manufacturer=maker,
        name="Different approved product display name",
        slug="different-product-display-name",
        model_number="H7IC16M6 UK",
    )
    db_session.add_all([maker, shop, product])
    db_session.flush()
    db_session.add_all(
        [
            ManufacturerAlias(manufacturer_id=maker.id, alias="Hotpoint"),
            RetailerAlias(retailer_id=shop.id, alias="Wren"),
        ]
    )
    db_session.flush()
    candidate = construct_reference(db_session)
    assert candidate.variants[0].product_links[0].product_id == product.id


def test_cleanup_preserves_reused_shared_identities_and_source(db_session):
    from app.db.models import ManufacturerAlias, RetailerAlias

    maker = Manufacturer(name="Hotpoint Shared", slug="hotpoint-shared")
    shop = Retailer(name="Wren Shared", slug="wren-shared")
    product = Product(
        manufacturer=maker,
        name="Shared different display",
        slug="shared-hotpoint-product",
        model_number="H7IC16M6 UK",
    )
    manifest = reference_manifest()
    source = Source(
        url=manifest["official_terms_url"],
        source_type="web_page",
        title=(
            "Hotpoint Wren Cashback terms — 2026 campaign; no explicit revision identifier observed"
        ),
        retrieved_at=datetime.fromisoformat(manifest["evidence"]["retrieved_at"]),
        verified_at=datetime.fromisoformat(manifest["evidence"]["verified_at"]),
    )
    db_session.add_all([maker, shop, product, source])
    db_session.flush()
    db_session.add_all(
        [
            ManufacturerAlias(manufacturer_id=maker.id, alias="Hotpoint"),
            RetailerAlias(retailer_id=shop.id, alias="Wren"),
        ]
    )
    db_session.flush()
    shared = (maker.id, shop.id, product.id, source.id)
    before = {
        kind: set(db_session.scalars(select(kind.id)))
        for kind in (Promotion, Source, Product, Retailer, Manufacturer)
    }
    candidate = construct_reference(db_session)
    owned = {
        kind: set(db_session.scalars(select(kind.id))) - before[kind]
        for kind in (Promotion, Source, Product, Retailer, Manufacturer)
    }
    delete_owned_rows(db_session, owned)
    assert candidate.variants[0].product_links[0].product_id == shared[2]
    assert shared[3] in {link.source_id for link in candidate.source_links}
    assert db_session.get(Manufacturer, shared[0]) is not None
    assert db_session.get(Retailer, shared[1]) is not None
    assert db_session.get(Product, shared[2]) is not None
    assert db_session.get(Source, shared[3]) is not None


def test_same_url_different_source_metadata_is_not_reused_or_mutated(db_session):
    maker = Manufacturer(name="Hotpoint", slug="hotpoint")
    shop = Retailer(name="Wren", slug="wren")
    source = Source(
        url=reference_manifest()["official_terms_url"],
        source_type="web_page",
        title="Different, unverified observation metadata",
        retrieved_at=datetime.fromisoformat("2026-10-12T13:57:18+00:00"),
        verified_at=None,
    )
    db_session.add_all([maker, shop, source])
    db_session.flush()
    before = (source.title, source.retrieved_at, source.verified_at)
    candidate = construct_reference(db_session)
    assert (
        next(link for link in candidate.source_links if link.role == "primary").source_id
        != source.id
    )
    assert (source.title, source.retrieved_at, source.verified_at) == before


def test_same_display_name_with_wrong_canonical_model_is_rejected(db_session):
    maker = Manufacturer(name="Hotpoint UK", slug="hotpoint-uk")
    shop = Retailer(name="Wren UK", slug="wren-uk")
    product = Product(
        manufacturer=maker,
        name=reference_manifest()["product"]["name"],
        slug="wrong-model-same-display-name",
        model_number="H7IC16M6",
    )
    db_session.add_all([maker, shop, product])
    db_session.flush()
    from app.db.models import ManufacturerAlias, ProductModelAlias, RetailerAlias

    db_session.add_all(
        [
            ManufacturerAlias(manufacturer_id=maker.id, alias="Hotpoint"),
            RetailerAlias(retailer_id=shop.id, alias="Wren"),
            ProductModelAlias(product_id=product.id, alias="H7IC16M6 UK"),
        ]
    )
    db_session.flush()
    before = _graph_ids(db_session)
    with pytest.raises(ValueError, match="Conflicting reference product identity"):
        construct_reference(db_session)
    assert _graph_ids(db_session) == before


@pytest.mark.parametrize(
    "field",
    [
        "source",
        "window",
        "purchase",
        "claim_wait_changed",
        "claim_wait_removed",
        "retailer",
        "limitation",
        "link",
        "requirements",
    ],
)
def test_replay_rejects_changed_graph_without_replacement(db_session, field):
    candidate = construct_reference(db_session)
    variant = candidate.variants[0]
    if field == "source":
        candidate.source_links[0].source.title = "Changed evidence"
    elif field == "window":
        candidate.claim_start_date = date(2026, 6, 12)
    elif field == "purchase":
        candidate.purchase_end_date = date(2026, 6, 11)
    elif field == "claim_wait_changed":
        candidate.claim_min_wait_days = 31
    elif field == "claim_wait_removed":
        candidate.claim_min_wait_days = None
    elif field == "retailer":
        other = Retailer(name="Other graph retailer", slug="other-graph-retailer")
        db_session.add(other)
        db_session.flush()
        variant.retailer_id = other.id
    elif field == "limitation":
        variant.benefits[0].description = "Unsupported claim guarantee"
    elif field == "link":
        db_session.delete(variant.product_links[0])
        db_session.flush()
        db_session.expire(variant, ["product_links"])
    else:
        from app.db.models import Requirement

        variant.requirements.append(
            Requirement(
                requirement_type="receipt",
                description="Synthetic unexpected requirement for replay conflict test",
            )
        )
    db_session.flush()
    before = _graph_ids(db_session)
    with pytest.raises(ValueError, match="Conflicting existing"):
        construct_reference(db_session)
    assert _graph_ids(db_session) == before
    assert candidate.status == PromotionStatus.REVIEW
    if field in {"claim_wait_changed", "claim_wait_removed"}:
        assert candidate.claim_min_wait_days == (31 if field == "claim_wait_changed" else None)


def test_mid_construction_failure_removes_all_owned_rows(db_session, monkeypatch):
    from app.db.reference import hotpoint as helper

    marker = Retailer(name="Retained caller", slug="retained-caller")
    db_session.add(marker)
    db_session.flush()
    before = _graph_ids(db_session)
    original = helper._resolve

    def fail_product(session, match, kind, attributes, **kwargs):
        if kind is Product:
            raise ValueError("mid-construction failure")
        return original(session, match, kind, attributes, **kwargs)

    monkeypatch.setattr(helper, "_resolve", fail_product)
    with pytest.raises(ValueError, match="mid-construction"):
        construct_reference(db_session)
    assert _graph_ids(db_session) == before
    assert db_session.get(Retailer, marker.id).name == "Retained caller"


def publish(factory, promotion_id):
    return change_promotion_status(
        partial(promotion_transaction, factory), promotion_id, PromotionStatus.ACTIVE
    )


def check(
    factory,
    purchase,
    evaluation,
    *,
    price=None,
    model="H7IC16M6 UK",
    retailer="Wren",
    brand="Hotpoint",
):
    with purchase_check_snapshot(factory) as (resolver, repository):
        return check_purchase(
            CheckPurchaseRequest(brand, model, retailer, purchase, price),
            evaluation_date=evaluation,
            identity_resolver=resolver,
            promotion_repository=repository,
        )


def test_persisted_gate_accepts_reviewed_candidate(reference):
    factory, promotion_id = reference
    publish(factory, promotion_id)
    with factory() as session:
        assert session.get(Promotion, promotion_id).status == PromotionStatus.ACTIVE


def test_historical_published_promotion_remains_explainable_after_expiry(reference):
    factory, promotion_id = reference
    publish(factory, promotion_id)
    change_promotion_status(
        partial(promotion_transaction, factory), promotion_id, PromotionStatus.EXPIRED
    )
    result = check(factory, date(2026, 5, 5), date(2026, 12, 4))
    assert isinstance(result, CheckPurchaseResult)
    offer = result.promotions[0]
    assert offer.promotion_id == promotion_id
    assert offer.promotion_status == PromotionStatus.EXPIRED
    assert offer.eligibility.classification == "ELIGIBLE"
    assert offer.benefits[0].cashback_reward_gbp == Decimal("75.00")
    assert offer.provenance.official_source_url == reference_manifest()["official_terms_url"]
    assert (
        check(factory, date(2026, 5, 5), date(2026, 12, 5)).promotions[0].eligibility.classification
        == "EXPIRED"
    )


def test_http_api_regression_uses_existing_contract(reference, postgres_engine):
    publish(reference[0], reference[1])
    manifest = reference_manifest()
    app = create_app(
        Settings(_env_file=None, APP_ENV="test", DATABASE_URL="postgresql+psycopg://unused/unused"),
        engine_factory=lambda _: postgres_engine,
    )
    app.dependency_overrides[uk_evaluation_date] = lambda: date(2026, 6, 3)
    body = {
        "brand": "Hotpoint",
        "model": "H7IC16M6 UK",
        "retailer": "Wren",
        "purchase_date": "2026-05-05",
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/eligibility/check", json=body)
        assert response.status_code == 200
        payload = response.json()
        offer = payload["promotions"][0]
        assert offer["eligibility"]["classification"] == "CLAIM_NOT_YET_OPEN"
        assert offer["promotion_status"] == "active"
        assert offer["claim_window"] == {
            "status": "not_yet_open",
            "opens_on": "2026-06-04",
            "deadline_on": "2026-12-04",
        }
        assert offer["benefits"][0]["cashback_reward_gbp"] == "75.00"
        assert {item["requirement_type"] for item in offer["requirements"]} == {
            "receipt",
            "serial_number",
            "registration",
        }
        assert offer["provenance"]["source_type"] == "web_page"
        assert offer["provenance"]["official_source_url"] == manifest["official_terms_url"]
        assert offer["provenance"]["claim_url"] == manifest["claim_url"]
        assert {source["role"]: source["url"] for source in offer["sources"]} == {
            "primary": manifest["official_terms_url"],
            "claim": manifest["claim_url"],
        }
        assert all(s["source_type"] == "web_page" for s in offer["sources"])
        app.dependency_overrides[uk_evaluation_date] = lambda: date(2026, 10, 12)
        response = client.post("/api/v1/eligibility/check", json=body)
        assert response.status_code == 200
        eligible = response.json()["promotions"][0]
        assert eligible["eligibility"]["classification"] == "ELIGIBLE"
        assert eligible["benefits"][0]["cashback_reward_gbp"] == "75.00"
        assert eligible["provenance"] == offer["provenance"]
        assert eligible["requirements"] == offer["requirements"]
        assert "wait after each purchase is enforced" in eligible["benefits"][0]["description"]
        app.dependency_overrides[uk_evaluation_date] = lambda: date(2026, 12, 5)
        response = client.post("/api/v1/eligibility/check", json=body)
        assert response.status_code == 200
        expired = response.json()["promotions"][0]
        assert expired["eligibility"]["classification"] == "EXPIRED"
        assert expired["provenance"] == eligible["provenance"]
        assert expired["benefits"][0]["cashback_reward_gbp"] == "75.00"
        response = client.post("/api/v1/eligibility/check", json={**body, "model": "WRONG-MODEL"})
        assert response.status_code == 200
        assert response.json()["outcome"] == "unresolved_identity"
        assert response.json()["unresolved_identity"]["field"] == "model"
        response = client.post(
            "/api/v1/eligibility/check", json={**body, "retailer": "Excluded test retailer"}
        )
        assert response.status_code == 200
        assert response.json()["no_match_reason"] == "no_matching_published_promotions"
        assert response.json()["promotions"] == []
        app.dependency_overrides[uk_evaluation_date] = lambda: date(2026, 10, 12)
        response = client.post(
            "/api/v1/eligibility/check", json={**body, "purchase_date": "2026-06-13"}
        )
        assert response.status_code == 200
        assert response.json()["promotions"] == []
        assert response.json()["no_match_reason"] == "no_matching_published_promotions"


def test_known_unlinked_identity_is_no_match_and_unknown_is_unresolved(reference):
    factory, promotion_id = reference
    publish(factory, promotion_id)
    with factory.begin() as session:
        candidate = session.get(Promotion, promotion_id)
        fake = Product(
            manufacturer_id=candidate.manufacturer_id,
            name="Synthetic unlinked washer",
            slug="synthetic-unlinked-washer",
            model_number="SYNTHETIC-UNLINKED",
        )
        shop = Retailer(name="Synthetic unrelated retailer", slug="synthetic-unrelated-retailer")
        session.add_all([fake, shop])
        session.flush()
        fake_id, shop_id = fake.id, shop.id
    try:
        known = check(
            factory,
            date(2026, 6, 1),
            date(2026, 10, 12),
            model="SYNTHETIC-UNLINKED",
            retailer="Wren",
        )
        assert known.promotions == ()
        assert known.no_match_reason == "no_matching_published_promotions"
        known_retailer = check(
            factory,
            date(2026, 6, 1),
            date(2026, 10, 12),
            model="H7IC16M6 UK",
            retailer="Synthetic unrelated retailer",
        )
        assert known_retailer.promotions == ()
        assert known_retailer.no_match_reason == "no_matching_published_promotions"
        result = check(factory, date(2026, 6, 1), date(2026, 10, 12), model="UNKNOWN-HOTPOINT")
        from app.application.promotion_candidate_matching import UnresolvedPurchaseIdentity

        assert isinstance(result, UnresolvedPurchaseIdentity)
        for kwargs in (
            {"brand": "UNKNOWN-HOTPOINT"},
            {"retailer": "UNKNOWN-WREN"},
            {"model": "H7IC16M6"},
        ):
            unresolved = check(factory, date(2026, 6, 1), date(2026, 10, 12), **kwargs)
            assert isinstance(unresolved, UnresolvedPurchaseIdentity)
        assert check(factory, date(2026, 6, 1), date(2026, 10, 12)).promotions
    finally:
        with factory.begin() as session:
            session.execute(delete(Product).where(Product.id == fake_id))
            session.execute(delete(Retailer).where(Retailer.id == shop_id))


def test_same_model_owned_by_other_manufacturer_is_not_reused(db_session):
    maker = Manufacturer(name="Unrelated manufacturer", slug="unrelated-manufacturer")
    product = Product(
        manufacturer=maker,
        name="Different maker same model text",
        slug="unrelated-same-model",
        model_number="H7IC16M6 UK",
    )
    db_session.add_all([maker, product])
    db_session.flush()
    candidate = construct_reference(db_session)
    assert candidate.manufacturer_id != maker.id
    assert candidate.variants[0].product_links[0].product_id != product.id
    assert db_session.get(Product, product.id).manufacturer_id == maker.id


@pytest.mark.parametrize("case", ["ambiguous", "wrong_model"])
def test_ambiguous_or_mislabelled_product_is_rejected(db_session, case):
    from app.db.models import ProductModelAlias

    maker = Manufacturer(name="Hotpoint", slug="hotpoint")
    shop = Retailer(name="Wren", slug="wren")
    first = Product(
        manufacturer=maker,
        name="Existing washer",
        slug="existing-washer",
        model_number="H7IC16M6 UK" if case == "ambiguous" else "H7IC16M6",
    )
    db_session.add_all([maker, shop, first])
    db_session.flush()
    alias_product = first
    if case == "ambiguous":
        alias_product = Product(
            manufacturer=maker,
            name="Conflicting washer",
            slug="conflicting-washer",
            model_number="CONFLICTING-WASHER",
        )
        db_session.add(alias_product)
        db_session.flush()
    db_session.add(ProductModelAlias(product_id=alias_product.id, alias="H7IC16M6 UK"))
    db_session.flush()
    before = _graph_ids(db_session)
    with pytest.raises(ValueError, match="Ambiguous|Conflicting"):
        construct_reference(db_session)
    assert _graph_ids(db_session) == before


def test_wrong_manufacturer_product_link_cannot_publish(db_session):
    from app.db.models import PromotionVariantProduct

    promotion = construct_reference(db_session)
    maker = Manufacturer(name="Wrong maker", slug="wrong-maker")
    product = Product(manufacturer=maker, name="Wrong maker washer", slug="wrong-maker-washer")
    promotion.variants[0].product_links.append(PromotionVariantProduct(product=product))
    db_session.flush()
    with pytest.raises(PromotionPublicationError) as error:
        change_promotion_status(
            partial(transaction, db_session), promotion.id, PromotionStatus.ACTIVE
        )
    assert "product_manufacturer_mismatch" in {issue.code for issue in error.value.report.issues}


def test_historical_limitations_are_retained_and_current_wait_is_enforced(reference):
    factory, promotion_id = reference
    publish(factory, promotion_id)
    f = reference_manifest()
    assert f["claim_delay_limitation"]["minimum_days_after_purchase"] == 30
    assert f["claim_delay_limitation"]["authoritative_runtime_rule"] is False
    offer = check(factory, date(2026, 6, 12), date(2026, 10, 12)).promotions[0]
    assert "30-day wait" in offer.benefits[0].benefit.description
    assert "wait after each purchase is enforced" in offer.benefits[0].benefit.description
    assert "No production publication" not in offer.benefits[0].benefit.description
    with factory() as session:
        candidate = session.get(Promotion, promotion_id)
        assert candidate.claim_start_offset_days is None
        assert candidate.claim_end_offset_days is None
        assert len(candidate.variants) == 1
        variant = candidate.variants[0]
        assert variant.product_links[0].product.model_number == "H7IC16M6 UK"
        assert variant.retailer.name == "Wren"
        claim = next(link.source for link in candidate.source_links if link.role == "claim")
        assert claim.title == f["evidence"]["claim_source_title"]
        assert "no claim submitted" in claim.title


@pytest.mark.parametrize("role", ["primary", "claim"])
def test_missing_required_source_blocks_publication_and_rolls_back(db_session, role):
    promotion = construct_reference(db_session)
    link = next(link for link in promotion.source_links if link.role == role)
    db_session.delete(link)
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(PromotionPublicationError):
        change_promotion_status(
            partial(transaction, db_session), promotion.id, PromotionStatus.ACTIVE
        )
    assert snapshot(db_session) == before
    db_session.expire_all()
    assert promotion.status == PromotionStatus.REVIEW


def test_publication_failure_rolls_back_entire_fixture_savepoint(db_session):
    marker = Retailer(name="Caller retained", slug="caller-retained")
    db_session.add(marker)
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(PromotionPublicationError):
        with db_session.begin_nested():
            promotion = construct_reference(db_session)
            promotion.source_links[0].source.verified_at = None
            db_session.flush()
            change_promotion_status(
                partial(transaction, db_session), promotion.id, PromotionStatus.ACTIVE
            )
    assert snapshot(db_session) == before
    assert db_session.get(Retailer, marker.id) is marker
