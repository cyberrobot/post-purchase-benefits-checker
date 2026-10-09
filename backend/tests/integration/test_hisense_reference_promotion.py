from datetime import date
from decimal import Decimal
from functools import partial

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import sessionmaker

from app.application.promotions import PromotionPublicationError, change_promotion_status
from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.db.models import Manufacturer, Product, Promotion, Retailer, Source
from app.db.repositories.promotions import promotion_transaction, purchase_check_snapshot
from app.domain.promotion_lifecycle import PromotionStatus
from tests.hisense_reference import construct_reference, reference_manifest

pytestmark = pytest.mark.integration


@pytest.fixture
def unverified_reference(postgres_engine, migrated_test_database):
    factory = sessionmaker(postgres_engine)
    with factory.begin() as session:
        promotion = construct_reference(session)
        promotion_id = promotion.id
        maker_id = promotion.manufacturer_id
        product_id = promotion.variants[0].product_links[0].product_id
        retailer_id = promotion.variants[0].retailer_id
        source_ids = [link.source_id for link in promotion.source_links]
    try:
        yield factory, promotion_id
    finally:
        with factory.begin() as session:
            session.execute(delete(Promotion).where(Promotion.id == promotion_id))
            session.execute(delete(Source).where(Source.id.in_(source_ids)))
            session.execute(delete(Product).where(Product.id == product_id))
            session.execute(delete(Retailer).where(Retailer.id == retailer_id))
            session.execute(delete(Manufacturer).where(Manufacturer.id == maker_id))


def test_candidate_is_review_only_and_persisted_publication_fails_closed(unverified_reference):
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
        assert all(source.verified_at is None for source in (link.source for link in promotion.source_links))

    with pytest.raises(PromotionPublicationError) as error:
        change_promotion_status(partial(promotion_transaction, factory), promotion_id,
                                PromotionStatus.ACTIVE)
    codes = {issue.code for issue in error.value.report.issues}
    assert "primary_source_unverified" in codes
    assert "claim_source_unverified" in codes
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
