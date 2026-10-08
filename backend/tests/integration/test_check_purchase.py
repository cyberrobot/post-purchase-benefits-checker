from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, event, text, update
from sqlalchemy.orm import Session

from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.application.purchase_check_details import PublishedPromotionDataError
from app.db.models import (
    Benefit,
    BenefitProductRewardValue,
    BenefitReward,
    Manufacturer,
    Product,
    Promotion,
    PromotionSource,
    PromotionVariant,
    PromotionVariantProduct,
    Requirement,
    Retailer,
    Source,
)
from app.db.repositories.promotions import purchase_check_snapshot
from app.domain.eligibility_result import EligibilityClassification

pytestmark = pytest.mark.integration
DAY = date(2024, 2, 29)
STAMP = datetime(2024, 1, 1, tzinfo=UTC)


@pytest.fixture
def published_graph(postgres_engine, migrated_test_database):
    tag = uuid4().hex
    with Session(postgres_engine) as session, session.begin():
        maker = Manufacturer(name=f"Maker {tag}", slug=f"maker-{tag}")
        shop = Retailer(name=f"Shop {tag}", slug=f"shop-{tag}")
        product = Product(
            manufacturer=maker, name="Product", slug=f"product-{tag}", model_number=tag
        )
        session.add_all([maker, shop, product])
        session.flush()
        sources = [
            Source(
                url=f"https://example.com/{tag}/{role}",
                source_type="web_page",
                retrieved_at=STAMP,
                verified_at=STAMP,
            )
            for role in ("primary", "claim", "supporting")
        ]
        session.add_all(sources)
        session.flush()
        promotions, variants = [], []
        for index, status in enumerate(("active", "expired", "review", "archived")):
            promotion = Promotion(
                manufacturer_id=maker.id,
                name=f"Offer {index}",
                slug=f"offer-{tag}-{index}",
                status=status,
                purchase_start_date=DAY,
                purchase_end_date=DAY,
                claim_start_date=DAY if index == 0 else None,
                claim_end_date=date(2024, 3, 30) if index == 0 else None,
                claim_start_offset_days=0 if index == 1 else None,
                claim_end_offset_days=30 if index == 1 else None,
                created_at=STAMP,
            )
            session.add(promotion)
            session.flush()
            promotions.append(promotion.id)
            session.add_all(
                [
                    PromotionSource(promotion_id=promotion.id, source_id=source.id, role=role)
                    for source, role in zip(
                        sources, ("primary", "claim", "supporting"), strict=True
                    )
                ]
            )
            for variant_index in range(2 if index == 0 else 1):
                variant = PromotionVariant(
                    promotion_id=promotion.id,
                    retailer_id=shop.id if variant_index == 0 else None,
                    code=f"v{variant_index}",
                    name=f"Variant {variant_index}",
                )
                session.add(variant)
                session.flush()
                variants.append(variant.id)
                session.add(
                    PromotionVariantProduct(promotion_variant_id=variant.id, product_id=product.id)
                )
                for kind in ("cashback", "extended_warranty", "free_gift"):
                    benefit = Benefit(promotion_variant_id=variant.id, benefit_type=kind, name=kind)
                    session.add(benefit)
                    session.flush()
                    if kind == "cashback":
                        reward_kind = (
                            "fixed_amount"
                            if index == 0 and variant_index == 0
                            else "percentage"
                            if index == 0
                            else "product_specific"
                        )
                        session.add(
                            BenefitReward(
                                benefit_id=benefit.id,
                                reward_type=reward_kind,
                                fixed_amount=Decimal("100")
                                if reward_kind == "fixed_amount"
                                else None,
                                percentage=Decimal("10") if reward_kind == "percentage" else None,
                            )
                        )
                        session.flush()
                        if reward_kind == "product_specific":
                            session.add(
                                BenefitProductRewardValue(
                                    benefit_id=benefit.id,
                                    product_id=product.id,
                                    amount=Decimal("42"),
                                )
                            )
                session.add_all(
                    [
                        Requirement(
                            promotion_variant_id=variant.id,
                            requirement_type=kind,
                            description="Passive instruction",
                        )
                        for kind in ("receipt", "receipt", "installation_evidence")
                    ]
                )
        request = CheckPurchaseRequest(maker.name, tag, shop.name, DAY, Decimal("199.99"))
        maker_id, shop_id, product_id = maker.id, shop.id, product.id
        source_ids = [source.id for source in sources]
    yield request, promotions, variants, product_id
    with postgres_engine.begin() as connection:
        connection.execute(delete(Promotion).where(Promotion.id.in_(promotions)))
        connection.execute(delete(Product).where(Product.id == product_id))
        connection.execute(delete(Manufacturer).where(Manufacturer.id == maker_id))
        connection.execute(delete(Retailer).where(Retailer.id == shop_id))
        connection.execute(delete(Source).where(Source.id.in_(source_ids)))


def test_complete_snapshot_materialised_no_writes(postgres_engine, published_graph):
    request, promotions, variants, product_id = published_graph
    statements = []

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split()[0].upper())

    event.listen(postgres_engine, "before_cursor_execute", record)
    try:
        with purchase_check_snapshot(lambda: Session(postgres_engine)) as (resolver, repository):
            assert (
                repository.session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            )
            assert repository.session.scalar(text("SHOW transaction_read_only")) == "on"
            result = check_purchase(
                request,
                evaluation_date=DAY,
                identity_resolver=resolver,
                promotion_repository=repository,
            )
        assert len(result.promotions) == 3
        assert set(value.promotion_variant_id for value in result.promotions) == set(variants[:3])
        for offer in result.promotions:
            assert offer.eligibility.classification == EligibilityClassification.ELIGIBLE
            assert len(offer.benefits) == 3
            assert len(offer.requirements) == 3
            assert len(offer.sources) == 3
            assert offer.provenance.verified_at == STAMP
            assert offer.claim_window.opens_on == DAY
        amounts = {
            benefit.cashback_reward_gbp
            for offer in result.promotions
            for benefit in offer.benefits
            if benefit.cashback_reward_gbp is not None
        }
        assert amounts == {Decimal("100"), Decimal("20.00"), Decimal("42")}
        assert not ({"INSERT", "UPDATE", "DELETE"} & set(statements))
        assert len(statements) < 25
    finally:
        event.remove(postgres_engine, "before_cursor_execute", record)


def test_snapshot_does_not_mix_concurrent_changes(postgres_engine, published_graph):
    request, promotions, _, _ = published_graph
    with purchase_check_snapshot(lambda: Session(postgres_engine)) as (resolver, repository):
        original = repository.find_promotion_candidates

        def concurrent_change(**kwargs):
            candidates = original(**kwargs)
            with postgres_engine.begin() as connection:
                connection.execute(
                    update(Promotion)
                    .where(Promotion.id == promotions[0])
                    .values(name="Changed concurrently")
                )
            return candidates

        repository.find_promotion_candidates = concurrent_change
        result = check_purchase(
            request,
            evaluation_date=DAY,
            identity_resolver=resolver,
            promotion_repository=repository,
        )
    assert all(
        offer.promotion_name == "Offer 0"
        for offer in result.promotions
        if offer.promotion_id == promotions[0]
    )
    with purchase_check_snapshot(lambda: Session(postgres_engine)) as (resolver, repository):
        changed = check_purchase(
            request,
            evaluation_date=DAY,
            identity_resolver=resolver,
            promotion_repository=repository,
        )
    assert all(
        offer.promotion_name == "Changed concurrently"
        for offer in changed.promotions
        if offer.promotion_id == promotions[0]
    )


def test_absent_window_and_invalid_published_content(postgres_engine, published_graph):
    request, promotions, _, _ = published_graph
    with postgres_engine.begin() as connection:
        connection.execute(
            update(Promotion)
            .where(Promotion.id == promotions[0])
            .values(claim_start_date=None, claim_end_date=None)
        )
    with purchase_check_snapshot(lambda: Session(postgres_engine)) as (resolver, repository):
        result = check_purchase(
            request,
            evaluation_date=DAY,
            identity_resolver=resolver,
            promotion_repository=repository,
        )
    missing = [offer for offer in result.promotions if offer.promotion_id == promotions[0]]
    assert all(
        offer.claim_window is None
        and offer.eligibility.classification == EligibilityClassification.POTENTIALLY_ELIGIBLE
        for offer in missing
    )
    with postgres_engine.begin() as connection:
        connection.execute(
            delete(PromotionSource).where(
                PromotionSource.promotion_id == promotions[0], PromotionSource.role == "claim"
            )
        )
    with purchase_check_snapshot(lambda: Session(postgres_engine)) as (resolver, repository):
        with pytest.raises(PublishedPromotionDataError):
            check_purchase(
                request,
                evaluation_date=DAY,
                identity_resolver=resolver,
                promotion_repository=repository,
            )


def test_snapshot_rejects_pending_session_before_sql(postgres_engine, migrated_test_database):
    session = Session(postgres_engine)
    session.add(Manufacturer(name="pending", slug="pending"))
    with pytest.raises(ValueError, match="fresh dedicated session"):
        with purchase_check_snapshot(lambda: session):
            pytest.fail("Should not yield dependencies")


def test_detail_reads_do_not_autoflush(db_session):
    from app.db.repositories.promotions import SqlAlchemyPromotionRepository

    pending = Manufacturer(name="not flushed", slug="not-flushed")
    db_session.add(pending)
    assert (
        SqlAlchemyPromotionRepository(db_session).load_check_purchase_candidates((uuid4(),)) == ()
    )
    assert pending.id is None
    assert pending in db_session.new


def test_detail_persistence_errors_are_safe():
    from sqlalchemy.exc import OperationalError

    from app.application.promotions import PromotionPersistenceError
    from app.db.repositories.promotions import SqlAlchemyPromotionRepository

    class FailedSession:
        from contextlib import nullcontext

        no_autoflush = nullcontext()

        def scalars(self, query):
            raise OperationalError("private SQL detail", {}, Exception("private cause"))

    with pytest.raises(PromotionPersistenceError, match="Promotion details query failed") as error:
        SqlAlchemyPromotionRepository(FailedSession()).load_check_purchase_candidates((uuid4(),))
    assert "private" not in str(error.value)
    assert error.value.__suppress_context__
