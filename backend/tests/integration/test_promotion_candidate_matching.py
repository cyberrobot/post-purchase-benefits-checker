from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import DataError

from app.application.identity_matching import IdentityResolver
from app.application.promotion_candidate_matching import (
    PromotionCandidate,
    PromotionCandidateSet,
    ResolvedPurchaseIdentity,
    UnresolvedPurchaseIdentity,
    match_promotion_candidates,
)
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check import CheckPurchaseRequest
from app.db.models import (
    Manufacturer,
    Product,
    Promotion,
    PromotionVariant,
    PromotionVariantProduct,
    Retailer,
    RetailerGroup,
    RetailerGroupMember,
    RetailerProductSku,
)
from app.db.repositories.identity_matching import SqlAlchemyIdentityRepository
from app.db.repositories.promotions import SqlAlchemyPromotionRepository
from app.domain.identity_normalisation import MatchStatus
from app.domain.promotion_lifecycle import PromotionStatus

pytestmark = pytest.mark.integration
DAY = date(2024, 2, 10)


@pytest.fixture
def catalogue(db_session):
    makers = [Manufacturer(name=f"Maker {i}", slug=f"maker-{i}") for i in range(2)]
    shops = [Retailer(name=f"Shop {i}", slug=f"shop-{i}") for i in range(2)]
    products = [
        Product(manufacturer=makers[0], name=f"Product {i}", slug=f"p-{i}", model_number=f"AB-{i}")
        for i in range(2)
    ]
    db_session.add_all(makers + shops + products)
    db_session.flush()
    return makers, shops, products


def seed(
    session,
    catalogue,
    *,
    status="active",
    maker=0,
    product=0,
    retailer=0,
    start=DAY,
    end=DAY,
    promotion_id=None,
    variant_id=None,
    created_at=None,
):
    makers, shops, products = catalogue
    promotion = Promotion(
        id=promotion_id or uuid4(),
        manufacturer_id=makers[maker].id,
        name="Offer",
        slug=f"offer-{uuid4().hex}",
        status=status,
        purchase_start_date=start,
        purchase_end_date=end,
        created_at=created_at or datetime(2024, 1, 1, tzinfo=UTC),
    )
    variant = PromotionVariant(
        id=variant_id or uuid4(),
        promotion=promotion,
        retailer_id=None if retailer is None else shops[retailer].id,
        code="default",
    )
    session.add_all([promotion, variant])
    session.flush()
    if product is not None:
        session.add(
            PromotionVariantProduct(
                promotion_variant_id=variant.id, product_id=products[product].id
            )
        )
        session.flush()
    return PromotionCandidate(
        promotion.id, variant.id, PromotionStatus(status), variant.retailer_id, start, end
    )


def query(session, catalogue, purchase_date=DAY):
    makers, shops, products = catalogue
    return SqlAlchemyPromotionRepository(session).find_promotion_candidates(
        manufacturer_id=makers[0].id,
        retailer_id=shops[0].id,
        product_id=products[0].id,
        purchase_date=purchase_date,
    )


@pytest.mark.parametrize("status", list(PromotionStatus))
def test_only_published_states(db_session, catalogue, status):
    candidate = seed(db_session, catalogue, status=status)
    assert query(db_session, catalogue) == (
        (candidate,) if status in (PromotionStatus.ACTIVE, PromotionStatus.EXPIRED) else ()
    )


@pytest.mark.parametrize(
    "changes,matched",
    [
        ({"maker": 1}, False),
        ({"product": 1}, False),
        ({"product": None}, False),
        ({"retailer": 1}, False),
        ({"retailer": None}, True),
    ],
)
def test_exact_applicability(db_session, catalogue, changes, matched):
    candidate = seed(db_session, catalogue, **changes)
    # Sharing a current retailer group does not make a different retailer applicable.
    group = RetailerGroup(name="Group", slug="group")
    db_session.add(group)
    db_session.flush()
    db_session.add_all(
        [
            RetailerGroupMember(retailer_group_id=group.id, retailer_id=shop.id)
            for shop in catalogue[1]
        ]
    )
    db_session.flush()
    assert query(db_session, catalogue) == ((candidate,) if matched else ())


@pytest.mark.parametrize(
    "start,end,purchase,matched",
    [
        (date(2024, 2, 1), DAY, date(2024, 2, 1), True),
        (date(2024, 2, 1), DAY, DAY, True),
        (DAY, DAY, date(2024, 2, 9), False),
        (DAY, DAY, date(2024, 2, 11), False),
        (None, DAY, date(2020, 1, 1), True),
        (DAY, None, date(2030, 1, 1), True),
        (None, None, date(2020, 1, 1), True),
        (None, DAY, date(2024, 2, 11), False),
        (DAY, None, date(2024, 2, 9), False),
    ],
)
def test_inclusive_and_missing_bounds(db_session, catalogue, start, end, purchase, matched):
    candidate = seed(db_session, catalogue, status="expired", start=start, end=end)
    assert query(db_session, catalogue, purchase) == ((candidate,) if matched else ())


def test_all_variants_and_stable_order(db_session, catalogue):
    old = seed(
        db_session, catalogue, promotion_id=UUID(int=1), created_at=datetime(2023, 1, 1, tzinfo=UTC)
    )
    second = seed(db_session, catalogue, promotion_id=UUID(int=20), variant_id=UUID(int=50))
    first = seed(db_session, catalogue, promotion_id=UUID(int=10), variant_id=UUID(int=40))
    variant = PromotionVariant(
        id=UUID(int=30), promotion_id=first.promotion_id, retailer_id=None, code="independent"
    )
    db_session.add(variant)
    db_session.flush()
    db_session.add(
        PromotionVariantProduct(promotion_variant_id=variant.id, product_id=catalogue[2][0].id)
    )
    db_session.flush()
    independent = replace(first, promotion_variant_id=variant.id, retailer_id=None)
    expected = (independent, first, second, old)
    assert query(db_session, catalogue) == expected
    db_session.expire_all()
    assert query(db_session, catalogue) == expected


def test_real_application_read_only_no_autoflush(db_session, catalogue):
    candidate = seed(db_session, catalogue, status="expired")
    maker, shop, product = catalogue[0][0], catalogue[1][0], catalogue[2][0]
    db_session.add(RetailerProductSku(retailer_id=shop.id, product_id=product.id, sku="AB-0"))
    db_session.flush()
    identity = ResolvedPurchaseIdentity(maker.id, shop.id, product.id)
    pending = Manufacturer(name="Pending", slug="pending")
    db_session.add(pending)
    statements = []
    connection = db_session.connection()

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(connection, "before_cursor_execute", capture)
    try:
        resolver = IdentityResolver(SqlAlchemyIdentityRepository(db_session))
        repository = SqlAlchemyPromotionRepository(db_session)
        for price in (None, Decimal("0"), Decimal("999.99")):
            request = CheckPurchaseRequest("Maker 0", " A B-0 ", "Shop 0", DAY, price)
            assert match_promotion_candidates(
                request, resolver, repository
            ) == PromotionCandidateSet(identity, (candidate,))
        assert match_promotion_candidates(
            replace(request, brand="Pending"), resolver, repository
        ) == UnresolvedPurchaseIdentity("brand", MatchStatus.NOT_FOUND, ())
        assert match_promotion_candidates(
            replace(request, purchase_date=date(2020, 1, 1)), resolver, repository
        ) == PromotionCandidateSet(identity, ())
        assert query(db_session, catalogue) == (candidate,)
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert pending.id is None
    assert statements and set(statements) == {"SELECT"}


def test_failed_transaction_is_safe_failure(db_session, catalogue):
    with db_session.begin_nested() as savepoint:
        with pytest.raises(DataError):
            db_session.execute(text("SELECT 1 / 0"))
        with pytest.raises(
            PromotionPersistenceError, match="^Promotion candidate query failed$"
        ) as error:
            query(db_session, catalogue)
        assert error.value.__cause__ is None
        savepoint.rollback()
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1


@pytest.mark.parametrize(
    "model,sku_product,matched", [("AB-0", 0, True), ("SKU-0", 0, True), ("AB-0", 1, False)]
)
def test_real_model_or_sku_resolution(db_session, catalogue, model, sku_product, matched):
    candidate = seed(db_session, catalogue)
    maker, shop, product = catalogue[0][0], catalogue[1][0], catalogue[2][0]
    db_session.add(
        RetailerProductSku(retailer_id=shop.id, product_id=catalogue[2][sku_product].id, sku=model)
    )
    db_session.flush()
    result = match_promotion_candidates(
        CheckPurchaseRequest("Maker 0", model, "Shop 0", DAY),
        IdentityResolver(SqlAlchemyIdentityRepository(db_session)),
        SqlAlchemyPromotionRepository(db_session),
    )
    if matched:
        assert result == PromotionCandidateSet(
            ResolvedPurchaseIdentity(maker.id, shop.id, product.id), (candidate,)
        )
    else:
        assert result == UnresolvedPurchaseIdentity(
            "model", MatchStatus.AMBIGUOUS, tuple(sorted(p.id for p in catalogue[2]))
        )
