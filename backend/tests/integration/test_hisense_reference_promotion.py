from datetime import date
from decimal import Decimal
from functools import partial

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from app.application.promotions import (
    PromotionPublicationError,
    change_promotion_status,
)
from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.db.models import Manufacturer, Product, Promotion, Retailer, Source
from app.db.repositories.promotions import (
    promotion_transaction,
    purchase_check_snapshot,
)
from app.domain.promotion_lifecycle import PromotionStatus
from tests.hisense_reference import construct_reference, reference_manifest

pytestmark = pytest.mark.integration


@pytest.fixture
def reference(postgres_engine, migrated_test_database):
    factory = sessionmaker(postgres_engine)
    with factory.begin() as session:
        before_ids = {
            "manufacturers": set(session.scalars(select(Manufacturer.id))),
            "products": set(session.scalars(select(Product.id))),
            "retailers": set(session.scalars(select(Retailer.id))),
            "sources": set(session.scalars(select(Source.id))),
        }
        promotion = construct_reference(session)
        promotion_id = promotion.id
        maker_id = promotion.manufacturer_id
        product_id = promotion.variants[0].product_links[0].product_id
        retailer_id = promotion.variants[0].retailer_id
        source_ids = [link.source_id for link in promotion.source_links]
        created_maker = maker_id if maker_id not in before_ids["manufacturers"] else None
        created_retailer = retailer_id if retailer_id not in before_ids["retailers"] else None
        created_product = product_id if product_id not in before_ids["products"] else None
        created_sources = set(source_ids) - before_ids["sources"]
    try:
        yield factory, promotion_id
    finally:
        with factory.begin() as session:
            session.execute(delete(Promotion).where(Promotion.id == promotion_id))
            if created_sources:
                session.execute(delete(Source).where(Source.id.in_(created_sources)))
            if created_product is not None:
                session.execute(delete(Product).where(Product.id == created_product))
            if created_retailer is not None:
                session.execute(delete(Retailer).where(Retailer.id == created_retailer))
            if created_maker is not None:
                session.execute(delete(Manufacturer).where(Manufacturer.id == created_maker))


def test_constructor_replay_preserves_review_graph(db_session):
    first = construct_reference(db_session)
    first_id = first.id
    db_session.flush()
    second = construct_reference(db_session)
    assert second.id == first_id
    assert second.status == PromotionStatus.REVIEW


def test_constructor_preflight_failure_rolls_back_savepoint_and_preserves_caller_state(
    db_session, monkeypatch
):
    from tests import hisense_reference as helper

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


def test_ambiguous_hisense_identity_rolls_back_candidate_graph(db_session):
    from app.db.models import ManufacturerAlias

    canonical = Manufacturer(name="Hisense", slug="hisense")
    other = Manufacturer(name="Hisense Alias Conflict", slug="hisense-alias-conflict")
    db_session.add_all([canonical, other])
    db_session.flush()
    db_session.add(ManufacturerAlias(manufacturer_id=other.id, alias="Hisense"))
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

    maker = Manufacturer(name="Hisense UK", slug="hisense-uk")
    shop = Retailer(name="Currys UK", slug="currys-uk")
    product = Product(
        manufacturer=maker,
        name="Existing washer",
        slug="existing-washer",
        model_number="wf7i 1248 bbr",
    )
    db_session.add_all([maker, shop, product])
    db_session.flush()
    db_session.add_all(
        [
            ManufacturerAlias(manufacturer_id=maker.id, alias="Hisense"),
            RetailerAlias(retailer_id=shop.id, alias="Currys"),
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


@pytest.mark.parametrize("field", ["source", "window", "limitation", "link", "requirements"])
def test_replay_rejects_changed_graph_without_replacement(db_session, field):
    candidate = construct_reference(db_session)
    variant = candidate.variants[0]
    if field == "source":
        candidate.source_links[0].source.title = "Changed evidence"
    elif field == "window":
        candidate.claim_start_date = date(2026, 10, 27)
    elif field == "limitation":
        variant.benefits[0].description = "Unsupported claim guarantee"
    elif field == "link":
        db_session.delete(variant.product_links[0])
        db_session.flush()
        db_session.expire(variant, ["product_links"])
    else:
        variant.requirements[0].description = "Changed receipt requirement"
    db_session.flush()
    before = _graph_ids(db_session)
    with pytest.raises(ValueError, match="Conflicting existing"):
        construct_reference(db_session)
    assert _graph_ids(db_session) == before
    assert candidate.status == PromotionStatus.REVIEW


def test_mid_construction_failure_removes_all_owned_rows(db_session, monkeypatch):
    from tests import hisense_reference as helper

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


def check(factory, purchase, evaluation, *, price=None, model="WF7I1248BBR", retailer="Currys"):
    with purchase_check_snapshot(factory) as (resolver, repository):
        return check_purchase(
            CheckPurchaseRequest("Hisense", model, retailer, purchase, price),
            evaluation_date=evaluation,
            identity_resolver=resolver,
            promotion_repository=repository,
        )


@pytest.mark.parametrize(
    "purchase,evaluation,classification",
    [
        (date(2026, 9, 9), date(2026, 9, 9), "CLAIM_NOT_YET_OPEN"),
        (date(2026, 9, 9), date(2026, 10, 9), "CLAIM_NOT_YET_OPEN"),
        (date(2026, 10, 27), date(2026, 10, 27), "CLAIM_NOT_YET_OPEN"),
        (date(2026, 10, 27), date(2026, 11, 26), "CLAIM_NOT_YET_OPEN"),
        (date(2026, 9, 9), date(2026, 11, 27), "ELIGIBLE"),
        (date(2026, 10, 27), date(2026, 11, 27), "ELIGIBLE"),
        (date(2026, 10, 27), date(2026, 12, 23), "ELIGIBLE"),
        (date(2026, 10, 27), date(2026, 12, 24), "ELIGIBLE"),
        (date(2026, 9, 9), date(2026, 12, 25), "EXPIRED"),
        (date(2026, 10, 27), date(2027, 1, 1), "EXPIRED"),
    ],
)
def test_persisted_fixed_window_matrix(reference, purchase, evaluation, classification):
    factory, promotion_id = reference
    publish(factory, promotion_id)
    result = check(factory, purchase, evaluation)
    assert len(result.promotions) == 1
    offer = result.promotions[0]
    assert offer.eligibility.classification == classification
    assert offer.promotion_id == promotion_id
    assert offer.promotion_status == PromotionStatus.ACTIVE
    assert [reason.code for reason in offer.eligibility.reasons] == [
        "all_configured_rules_satisfied",
        {
            "CLAIM_NOT_YET_OPEN": "claim_window_not_yet_open",
            "ELIGIBLE": "claim_window_open",
            "EXPIRED": "claim_window_expired",
        }[classification],
    ]
    assert offer.provenance.official_source_url == reference_manifest()["official_terms_url"]
    assert {source.role for source in offer.sources} == {"primary", "claim", "supporting"}
    assert {source.url for source in offer.sources} == {
        item["url"] for item in reference_manifest()["evidence"]["observations"]
    }
    assert all(
        source.verified_at >= source.retrieved_at and source.retrieved_at.tzinfo
        for source in offer.sources
    )
    assert offer.explanation == (
        "The recorded eligibility rules match this purchase.",
        {
            "CLAIM_NOT_YET_OPEN": "Claiming opens on 2026-11-27.",
            "ELIGIBLE": "The claim window is open.",
            "EXPIRED": "The claim deadline has passed.",
        }[classification],
    )
    assert offer.claim_window.opens_on == date(2026, 11, 27)
    assert offer.claim_window.deadline_on == date(2026, 12, 24)
    assert offer.benefits[0].cashback_reward_gbp == Decimal("100.00")
    assert {r.requirement_type for r in offer.requirements} == {"receipt", "serial_number"}
    assert offer.provenance.claim_url == reference_manifest()["claim_url"]
    with factory() as session:
        assert session.get(Promotion, promotion_id).status == PromotionStatus.ACTIVE


@pytest.mark.parametrize("purchase", [date(2026, 9, 8), date(2026, 10, 28)])
def test_outside_purchase_window_has_no_matching_offer(reference, purchase):
    factory, promotion_id = reference
    publish(factory, promotion_id)
    result = check(factory, purchase, max(purchase, date(2026, 9, 9)))
    assert result.promotions == ()
    assert result.no_match_reason == "no_matching_published_promotions"


@pytest.mark.parametrize("price", [None, Decimal("1.00"), Decimal("2000.00")])
def test_reward_is_fixed_independent_of_purchase_price(reference, price):
    factory, promotion_id = reference
    publish(factory, promotion_id)
    assert check(factory, date(2026, 10, 1), date(2026, 11, 27), price=price).promotions[
        0
    ].benefits[0].cashback_reward_gbp == Decimal("100.00")


def test_review_candidate_invisible_then_explicit_retirement_preserves_history(reference):
    factory, promotion_id = reference
    assert check(factory, date(2026, 10, 1), date(2026, 11, 27)).promotions == ()
    publish(factory, promotion_id)
    first = check(factory, date(2026, 10, 1), date(2026, 11, 27)).promotions[0]
    with factory.begin() as session:
        assert construct_reference(session).status == PromotionStatus.ACTIVE
    change_promotion_status(
        partial(promotion_transaction, factory), promotion_id, PromotionStatus.EXPIRED
    )
    after = check(factory, date(2026, 10, 1), date(2026, 11, 27)).promotions[0]
    assert after.eligibility == first.eligibility
    assert after.sources == first.sources
    assert after.provenance == first.provenance
    assert after.promotion_status == PromotionStatus.EXPIRED
    assert (
        check(factory, date(2026, 10, 1), date(2026, 12, 25))
        .promotions[0]
        .eligibility.classification
        == "EXPIRED"
    )
    with factory.begin() as session:
        assert construct_reference(session).status == PromotionStatus.EXPIRED


@pytest.mark.parametrize(
    "failure", ["missing_primary", "unverified_primary", "missing_claim", "unverified_claim"]
)
def test_persisted_gate_rejects_invalid_source_authority(reference, failure):
    factory, promotion_id = reference
    with factory.begin() as session:
        candidate = session.get(Promotion, promotion_id)
        role = "primary" if "primary" in failure else "claim"
        link = next(link for link in candidate.source_links if link.role == role)
        if failure.startswith("missing"):
            session.delete(link)
        else:
            link.source.verified_at = None
    with pytest.raises(PromotionPublicationError):
        publish(factory, promotion_id)
    with factory() as session:
        assert session.get(Promotion, promotion_id).status == PromotionStatus.REVIEW


@pytest.mark.parametrize(
    "evaluation_date",
    [date(2026, 10, 9), date(2026, 11, 26), date(2026, 11, 27), date(2026, 12, 25)],
)
def test_http_published_reference_is_reproducible_and_read_only(
    reference, postgres_engine, evaluation_date
):
    from fastapi.testclient import TestClient
    from sqlalchemy import event

    from app.api.eligibility import uk_evaluation_date
    from app.core.config import Settings
    from app.main import create_app

    factory, promotion_id = reference
    publish(factory, promotion_id)
    app = create_app(
        Settings(_env_file=None, APP_ENV="test", DATABASE_URL="postgresql+psycopg://unused/unused"),
        engine_factory=lambda _: postgres_engine,
    )
    app.dependency_overrides[uk_evaluation_date] = lambda: evaluation_date
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split()[0].upper())

    with TestClient(app) as client:
        event.listen(postgres_engine, "before_cursor_execute", record)
        try:
            body = {
                "brand": "Hisense",
                "model": "WF7I1248BBR",
                "retailer": "Currys",
                "purchase_date": "2026-09-09"
                if evaluation_date == date(2026, 10, 9)
                else "2026-10-27",
            }
            response = client.post("/api/v1/eligibility/check", json=body)
            assert response.status_code == 200
            offer = response.json()["promotions"][0]
            expected = (
                "CLAIM_NOT_YET_OPEN"
                if evaluation_date < date(2026, 11, 27)
                else "EXPIRED"
                if evaluation_date > date(2026, 12, 24)
                else "ELIGIBLE"
            )
            assert offer["eligibility"]["classification"] == expected
            assert offer["benefits"][0]["cashback_reward_gbp"] == "100.00"
            assert offer["claim_window"]["opens_on"] == "2026-11-27"
            assert offer["claim_window"]["deadline_on"] == "2026-12-24"
            assert offer["provenance"]["claim_url"] == reference_manifest()["claim_url"]
            assert offer["promotion_status"] == "active"
            if expected == "ELIGIBLE":
                requirements = {
                    item["requirement_type"]: item["description"] for item in offer["requirements"]
                }
                assert set(requirements) == {"receipt", "serial_number"}
                assert "purchase price" in requirements["receipt"].lower()
                manifest = reference_manifest()
                assert {item["url"] for item in offer["sources"]} == {
                    item["url"] for item in manifest["evidence"]["observations"]
                }
                assert all(item["verified_at"] is not None for item in offer["sources"])
            assert client.post("/api/v1/eligibility/check", json=body).json() == response.json()
            outside = client.post(
                "/api/v1/eligibility/check", json={**body, "purchase_date": "2026-10-28"}
            )
            assert outside.status_code == 200
            assert outside.json()["promotions"] == []
            assert outside.json()["no_match_reason"] == "no_matching_published_promotions"
            assert not {"INSERT", "UPDATE", "DELETE", "COMMIT"}.intersection(statements)
        finally:
            event.remove(postgres_engine, "before_cursor_execute", record)
    with factory.begin() as session:
        synthetic = Retailer(
            name="Synthetic unrelated retailer", slug="synthetic-unrelated-retailer"
        )
        session.add(synthetic)
        session.flush()
        synthetic_id = synthetic.id
    try:
        with TestClient(app) as client:
            wrong_retailer = client.post(
                "/api/v1/eligibility/check",
                json={
                    "brand": "Hisense",
                    "model": "WF7I1248BBR",
                    "retailer": "Synthetic unrelated retailer",
                    "purchase_date": "2026-10-01",
                },
            )
            assert wrong_retailer.status_code == 200
            assert wrong_retailer.json()["promotions"] == []
            assert wrong_retailer.json()["no_match_reason"] == "no_matching_published_promotions"
    finally:
        with factory.begin() as session:
            session.execute(delete(Retailer).where(Retailer.id == synthetic_id))
    with factory() as session:
        assert session.get(Promotion, promotion_id).status == PromotionStatus.ACTIVE


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
        for model, retailer in [
            ("SYNTHETIC-UNLINKED", "Currys"),
            ("WF7I1248BBR", "Synthetic unrelated retailer"),
        ]:
            result = check(
                factory, date(2026, 10, 1), date(2026, 11, 27), model=model, retailer=retailer
            )
            assert result.promotions == ()
            assert result.no_match_reason == "no_matching_published_promotions"
        result = check(factory, date(2026, 10, 1), date(2026, 11, 27), model="UNKNOWN-HISENSE")
        from app.application.promotion_candidate_matching import UnresolvedPurchaseIdentity

        assert isinstance(result, UnresolvedPurchaseIdentity)
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
        model_number="WF7I1248BBR",
    )
    db_session.add_all([maker, product])
    db_session.flush()
    candidate = construct_reference(db_session)
    assert candidate.manufacturer_id != maker.id
    assert candidate.variants[0].product_links[0].product_id != product.id
    assert db_session.get(Product, product.id).manufacturer_id == maker.id


def test_cross_campaign_graph_does_not_change_autumn_reward_or_sources(reference):
    from datetime import UTC, datetime

    from app.db.models import (
        Benefit,
        BenefitReward,
        PromotionSource,
        PromotionVariant,
        PromotionVariantProduct,
    )

    factory, autumn_id = reference
    publish(factory, autumn_id)
    with factory.begin() as session:
        autumn = session.get(Promotion, autumn_id)
        product_id = autumn.variants[0].product_links[0].product_id
        retailer_id = autumn.variants[0].retailer_id
        earlier = Promotion(
            manufacturer_id=autumn.manufacturer_id,
            name="Synthetic cross-campaign collision test fixture",
            slug="synthetic-cross-campaign-collision-test",
            status=PromotionStatus.REVIEW,
            purchase_start_date=date(2026, 5, 1),
            purchase_end_date=date(2026, 6, 30),
            claim_start_date=date(2026, 7, 1),
            claim_end_date=date(2026, 7, 31),
        )
        earlier.variants = [
            PromotionVariant(
                code="synthetic-overlap",
                name="Synthetic GBP 150 cross-campaign collision fixture",
                retailer_id=retailer_id,
                product_links=[PromotionVariantProduct(product_id=product_id)],
                benefits=[
                    Benefit(
                        benefit_type="cashback",
                        name="Synthetic GBP 150 test reward; no official evidence",
                        reward=BenefitReward(
                            reward_type="fixed_amount", fixed_amount=Decimal("150.00")
                        ),
                    )
                ],
            )
        ]
        synthetic_source = Source(
            url="https://example.test/synthetic-cross-campaign-fixture",
            source_type="web_page",
            title="Synthetic test fixture; not manufacturer evidence",
            retrieved_at=datetime(2026, 10, 9, tzinfo=UTC),
            verified_at=datetime(2026, 10, 9, tzinfo=UTC),
        )
        synthetic_claim_source = Source(
            url="https://example.test/synthetic-claim-fixture",
            source_type="web_page",
            title="Synthetic test fixture claim destination; not manufacturer evidence",
            retrieved_at=datetime(2026, 10, 9, tzinfo=UTC),
            verified_at=datetime(2026, 10, 9, tzinfo=UTC),
        )
        earlier.source_links = [
            PromotionSource(role="primary", source=synthetic_source),
            PromotionSource(role="claim", source=synthetic_claim_source),
        ]
        session.add(earlier)
        session.flush()
        earlier_id = earlier.id
        synthetic_source_ids = [synthetic_source.id, synthetic_claim_source.id]

    # This distinct fixture exercises the same product and retailer. It is published
    # through the normal gate with explicitly synthetic provenance, never official evidence.
    try:
        publish(factory, earlier_id)
        result = check(factory, date(2026, 10, 1), date(2026, 11, 27))
        assert len(result.promotions) == 1
        autumn_offer = result.promotions[0]
        assert autumn_offer.promotion_id == autumn_id
        assert autumn_offer.eligibility.classification == "ELIGIBLE"
        assert autumn_offer.benefits[0].cashback_reward_gbp == Decimal("100.00")
        assert (
            autumn_offer.provenance.official_source_url
            == reference_manifest()["official_terms_url"]
        )
        assert all(
            source.url != "https://example.test/synthetic-cross-campaign-fixture"
            for source in autumn_offer.sources
        )
    finally:
        with factory.begin() as session:
            session.execute(
                delete(PromotionSource).where(PromotionSource.source_id.in_(synthetic_source_ids))
            )
            session.execute(delete(Promotion).where(Promotion.id == earlier_id))
            session.execute(delete(Source).where(Source.id.in_(synthetic_source_ids)))


@pytest.mark.parametrize("case", ["ambiguous", "wrong_model"])
def test_ambiguous_or_mislabelled_product_is_rejected(db_session, case):
    from app.db.models import ProductModelAlias

    maker = Manufacturer(name="Hisense", slug="hisense")
    shop = Retailer(name="Currys", slug="currys")
    first = Product(
        manufacturer=maker,
        name="Existing washer",
        slug="existing-washer",
        model_number="WF7I1248BBR" if case == "ambiguous" else "WF7I1248BBA",
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
    db_session.add(ProductModelAlias(product_id=alias_product.id, alias="WF7I1248BBR"))
    db_session.flush()
    before = _graph_ids(db_session)
    with pytest.raises(ValueError, match="Ambiguous|Conflicting"):
        construct_reference(db_session)
    assert _graph_ids(db_session) == before


def test_wrong_manufacturer_product_link_cannot_publish(reference):
    from app.db.models import PromotionVariantProduct

    factory, promotion_id = reference
    with factory.begin() as session:
        maker = Manufacturer(name="Wrong maker", slug="wrong-maker")
        product = Product(manufacturer=maker, name="Wrong maker washer", slug="wrong-maker-washer")
        candidate = session.get(Promotion, promotion_id)
        candidate.variants[0].product_links.append(PromotionVariantProduct(product=product))
        session.flush()
        maker_id, product_id = maker.id, product.id
    try:
        with pytest.raises(PromotionPublicationError) as error:
            publish(factory, promotion_id)
        assert "product_manufacturer_mismatch" in {
            issue.code for issue in error.value.report.issues
        }
    finally:
        with factory.begin() as session:
            session.execute(
                delete(PromotionVariantProduct).where(
                    PromotionVariantProduct.product_id == product_id
                )
            )
            session.execute(delete(Product).where(Product.id == product_id))
            session.execute(delete(Manufacturer).where(Manufacturer.id == maker_id))
