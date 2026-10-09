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
def unverified_reference(postgres_engine, migrated_test_database):
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


def test_candidate_is_review_only_and_persisted_publication_fails_closed(
    unverified_reference,
):
    factory, promotion_id = unverified_reference
    with factory() as session:
        promotion = session.get(Promotion, promotion_id)
        assert promotion.status == PromotionStatus.REVIEW
        assert promotion.claim_start_date == date(2026, 11, 27)
        assert promotion.claim_end_date == date(2026, 12, 24)
        assert promotion.claim_start_offset_days is None
        assert promotion.claim_end_offset_days is None
        assert len(promotion.variants) == 1
        assert promotion.variants[0].benefits[0].reward.fixed_amount == Decimal("100.00")
        assert all(
            source.verified_at is None
            for source in (link.source for link in promotion.source_links)
        )

    with pytest.raises(PromotionPublicationError) as error:
        change_promotion_status(
            partial(promotion_transaction, factory),
            promotion_id,
            PromotionStatus.ACTIVE,
        )
    codes = {issue.code for issue in error.value.report.issues}
    assert "missing_primary_source" in codes
    assert "missing_claim_source" in codes
    with factory() as session:
        assert session.get(Promotion, promotion_id).status == PromotionStatus.REVIEW


def test_unverified_candidate_is_invisible_to_purchase_check(unverified_reference):
    factory, _ = unverified_reference
    manifest = reference_manifest()
    with purchase_check_snapshot(factory) as (resolver, repository):
        result = check_purchase(
            CheckPurchaseRequest(
                "Hisense", "WF7I1248BBR", "Currys", date(2026, 10, 27), Decimal("1.00")
            ),
            evaluation_date=date(2026, 11, 27),
            identity_resolver=resolver,
            promotion_repository=repository,
        )
    assert result.promotions == ()
    assert result.no_match_reason == "no_matching_published_promotions"
    assert manifest["evidence_status"] == "unverified_review_candidate"


def test_candidate_constructor_replay_preserves_unverified_review_graph(db_session):
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
    before_ids = set(db_session.scalars(select(Promotion.id)))

    def fail(_candidate):
        raise ValueError("simulated candidate preflight failure")

    monkeypatch.setattr(helper, "validate_candidate_promotion", fail)
    with pytest.raises(ValueError, match="simulated candidate preflight failure"):
        construct_reference(db_session)

    assert marker in db_session
    assert set(db_session.scalars(select(Promotion.id))) == before_ids
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
