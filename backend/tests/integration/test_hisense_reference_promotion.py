from datetime import date, datetime
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
        owned_types = (Promotion, Source, Product, Retailer, Manufacturer)
        before = {kind: set(session.scalars(select(kind.id))) for kind in owned_types}
        promotion = construct_reference(session)
        promotion_id = promotion.id
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


def test_unverified_candidate_cannot_publish_and_is_invisible(reference):
    factory, promotion_id = reference
    with factory() as session:
        candidate = session.get(Promotion, promotion_id)
        assert candidate.status == PromotionStatus.REVIEW
        assert [link.role for link in candidate.source_links] == ["supporting"]
        assert all(link.source.verified_at is None for link in candidate.source_links)
        manifest = reference_manifest()
        assert {link.source.url for link in candidate.source_links} == {
            item["url"]
            for item in manifest["evidence"]["historical_observations"]
            if item["url"] == manifest["retailer_corroboration_url"] and item["retrieved_at"]
        }
        assert all(item.role not in {"primary", "claim"} for item in candidate.source_links)
    with pytest.raises(PromotionPublicationError) as error:
        publish(factory, promotion_id)
    assert {issue.code for issue in error.value.report.issues} >= {
        "missing_primary_source",
        "missing_claim_source",
    }
    assert "unverified_primary_source" not in {issue.code for issue in error.value.report.issues}
    assert "unverified_claim_source" not in {issue.code for issue in error.value.report.issues}
    with factory() as session:
        assert session.get(Promotion, promotion_id).status == PromotionStatus.REVIEW
    result = check(factory, date(2026, 10, 1), date(2026, 11, 27))
    assert result.promotions == ()
    assert result.no_match_reason == "no_matching_published_promotions"


def test_candidate_replay_reuses_unverified_supporting_source(reference):
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


def test_exact_model_reuses_product_with_different_display_name(db_session):
    from app.db.models import ManufacturerAlias, RetailerAlias

    maker = Manufacturer(name="Hisense UK", slug="hisense-uk")
    shop = Retailer(name="Currys UK", slug="currys-uk")
    product = Product(
        manufacturer=maker,
        name="Different approved product display name",
        slug="different-product-display-name",
        model_number="WF7I1248BBR",
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
    candidate = construct_reference(db_session)
    assert candidate.variants[0].product_links[0].product_id == product.id


def test_cleanup_preserves_reused_shared_identities_and_source(db_session):
    from app.db.models import ManufacturerAlias, RetailerAlias

    maker = Manufacturer(name="Hisense Shared", slug="hisense-shared")
    shop = Retailer(name="Currys Shared", slug="currys-shared")
    product = Product(
        manufacturer=maker,
        name="Shared different display",
        slug="shared-hisense-product",
        model_number="WF7I1248BBR",
    )
    source = Source(
        url=reference_manifest()["retailer_corroboration_url"],
        source_type="web_page",
        title="Observed Currys product summary; campaign rules unverified",
        retrieved_at=datetime.fromisoformat("2026-10-09T12:29:00+00:00"),
        verified_at=None,
    )
    db_session.add_all([maker, shop, product, source])
    db_session.flush()
    db_session.add_all(
        [
            ManufacturerAlias(manufacturer_id=maker.id, alias="Hisense"),
            RetailerAlias(retailer_id=shop.id, alias="Currys"),
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
    assert candidate.source_links[0].source_id == shared[3]
    assert db_session.get(Manufacturer, shared[0]) is not None
    assert db_session.get(Retailer, shared[1]) is not None
    assert db_session.get(Product, shared[2]) is not None
    assert db_session.get(Source, shared[3]) is not None


def test_same_display_name_with_wrong_canonical_model_is_rejected(db_session):
    maker = Manufacturer(name="Hisense UK", slug="hisense-uk")
    shop = Retailer(name="Currys UK", slug="currys-uk")
    product = Product(
        manufacturer=maker,
        name=reference_manifest()["product"]["name"],
        slug="wrong-model-same-display-name",
        model_number="WF7I1248BBA",
    )
    db_session.add_all([maker, shop, product])
    db_session.flush()
    from app.db.models import ManufacturerAlias, ProductModelAlias, RetailerAlias

    db_session.add_all(
        [
            ManufacturerAlias(manufacturer_id=maker.id, alias="Hisense"),
            RetailerAlias(retailer_id=shop.id, alias="Currys"),
            ProductModelAlias(product_id=product.id, alias="WF7I1248BBR"),
        ]
    )
    db_session.flush()
    before = _graph_ids(db_session)
    with pytest.raises(ValueError, match="Conflicting reference product identity"):
        construct_reference(db_session)
    assert _graph_ids(db_session) == before


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


def test_persisted_gate_rejects_unverified_candidate(reference):
    factory, promotion_id = reference
    with pytest.raises(PromotionPublicationError):
        publish(factory, promotion_id)
    with factory() as session:
        assert session.get(Promotion, promotion_id).status == PromotionStatus.REVIEW


def test_known_unlinked_identity_is_no_match_and_unknown_is_unresolved(reference):
    factory, promotion_id = reference
    with pytest.raises(PromotionPublicationError):
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
        result = check(factory, date(2026, 10, 1), date(2026, 11, 27), model="UNKNOWN-HISENSE")
        from app.application.promotion_candidate_matching import UnresolvedPurchaseIdentity

        assert isinstance(result, UnresolvedPurchaseIdentity)
        assert check(factory, date(2026, 10, 1), date(2026, 11, 27)).promotions == ()
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
