from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from functools import partial

import pytest
from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.application.promotions import (
    PromotionPersistenceError,
    PromotionPublicationError,
    change_promotion_status,
)
from app.db.models import BenefitReward, Manufacturer, Product, PromotionVariantProduct
from app.db.repositories.promotions import SqlAlchemyPromotionRepository, promotion_transaction
from app.domain.promotion_lifecycle import PromotionStatus as S
from tests.integration.test_core_promotion_schema import graph as complete_graph  # noqa: F401
from tests.integration.test_promotion_lifecycle import snapshot, transaction

pytestmark = pytest.mark.integration


def make_publishable(graph):
    graph.status = S.REVIEW
    graph.claim_start_offset_days = 0
    graph.claim_end_offset_days = 30
    for variant in graph.variants:
        for benefit in variant.benefits:
            if benefit.benefit_type == "cashback":
                benefit.reward = BenefitReward(
                    reward_type="fixed_amount", fixed_amount=Decimal("50.00")
                )
    return graph


@pytest.fixture
def graph(request, db_session):
    graph = make_publishable(request.getfixturevalue("complete_graph"))
    db_session.flush()
    return graph


def test_publication_whole_graph(db_session, graph):
    before = snapshot(db_session)
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed
    db_session.expire_all()
    assert SqlAlchemyPromotionRepository(db_session).get_promotion(graph.id).status == S.ACTIVE
    after = snapshot(db_session)
    assert all(before[t] == after[t] for t in before.keys() - {"promotions"})


@pytest.mark.parametrize(
    "case,code",
    [
        ("variants", "missing_variant"),
        ("products", "missing_product"),
        ("benefits", "missing_benefit"),
        ("reward", "missing_cashback_reward"),
        ("claim", "missing_claim_window"),
        ("source", "primary_source_unverified"),
        ("manufacturer", "product_manufacturer_mismatch"),
    ],
)
def test_rejection_no_writes(db_session, graph, case, code):
    variant = graph.variants[0]
    if case == "variants":
        for row in list(graph.variants):
            db_session.delete(row)
    elif case == "products":
        for row in variant.product_links:
            db_session.delete(row)
    elif case == "benefits":
        for row in variant.benefits:
            db_session.delete(row)
    elif case == "reward":
        db_session.delete(next(b for b in variant.benefits if b.benefit_type == "cashback").reward)
    elif case == "claim":
        graph.claim_start_offset_days = graph.claim_end_offset_days = None
    elif case == "source":
        next(
            link.source for link in graph.source_links if link.role == "primary"
        ).verified_at = None
    else:
        other = Manufacturer(name="Other", slug="other")
        product = Product(manufacturer=other, name="Other", slug="other")
        variant.product_links.append(PromotionVariantProduct(product=product))
    db_session.flush()
    db_session.expire_all()
    before = snapshot(db_session)
    with pytest.raises(PromotionPublicationError) as error:
        change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE)
    assert code in {i.code for i in error.value.report.issues}
    assert snapshot(db_session) == before
    assert SqlAlchemyPromotionRepository(db_session).get_promotion(graph.id).status == S.REVIEW


def test_preflight_snapshot_cannot_approve_changed_graph(db_session, graph):
    from app.domain.promotion_validation import validate_promotion_for_publication

    repository = SqlAlchemyPromotionRepository(db_session)
    assert validate_promotion_for_publication(
        repository.get_publication_snapshot_for_update(graph.id)
    ).can_publish
    graph.claim_start_offset_days = graph.claim_end_offset_days = None
    db_session.flush()
    with pytest.raises(PromotionPublicationError):
        change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE)


@pytest.mark.parametrize("stage", ["read", "commit"])
def test_safe_failure_rolls_back(db_session, graph, stage):
    before = snapshot(db_session)

    def fail_read(connection, cursor, statement, *args):
        if "FOR UPDATE" in statement:
            raise OperationalError("private SQL", {}, Exception("private"))

    def fail_commit(*args):
        raise OperationalError("private SQL", {}, Exception("private"))

    def factory():
        return Session(bind=db_session.connection(), join_transaction_mode="create_savepoint")

    target, name, callback = (
        (db_session.bind, "before_cursor_execute", fail_read)
        if stage == "read"
        else (Session, "before_commit", fail_commit)
    )
    event.listen(target, name, callback)
    try:
        with pytest.raises(PromotionPersistenceError) as error:
            change_promotion_status(partial(promotion_transaction, factory), graph.id, S.ACTIVE)
        assert "private" not in str(error.value)
    finally:
        event.remove(target, name, callback)
    assert snapshot(db_session) == before


def test_lock_is_taken_before_association_reads(db_session, graph):
    statements = []

    def capture(connection, cursor, statement, *args):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", capture)
    try:
        SqlAlchemyPromotionRepository(db_session).get_publication_snapshot_for_update(graph.id)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", capture)
    lock_index = next(i for i, sql in enumerate(statements) if "FOR UPDATE" in sql)
    assert all(
        i > lock_index
        for i, sql in enumerate(statements)
        if "FROM promotion_variants" in sql or "FROM promotion_sources" in sql
    )


@pytest.fixture
def committed_graph(postgres_engine, migrated_test_database):
    from datetime import UTC, datetime
    from uuid import uuid4

    from sqlalchemy import delete
    from sqlalchemy.orm import sessionmaker

    from app.db.models import Benefit, Promotion, PromotionSource, PromotionVariant, Source

    factory = sessionmaker(postgres_engine)
    identity, manufacturer_id = uuid4(), uuid4()
    source_ids = [uuid4(), uuid4()]
    with factory.begin() as session:
        manufacturer = Manufacturer(
            id=manufacturer_id, name="Concurrent", slug=str(manufacturer_id)
        )
        product = Product(manufacturer=manufacturer, name="Product", slug="product")
        promotion = Promotion(
            id=identity,
            manufacturer=manufacturer,
            name="Campaign",
            slug="campaign",
            status=S.REVIEW,
            purchase_start_date=date(2026, 10, 1),
            claim_start_offset_days=0,
            claim_end_offset_days=30,
        )
        variant = PromotionVariant(promotion=promotion, code="all")
        variant.product_links = [PromotionVariantProduct(product=product)]
        variant.benefits = [Benefit(benefit_type="free_gift", name="Gift")]
        now = datetime(2026, 10, 1, tzinfo=UTC)
        promotion.source_links = [
            PromotionSource(
                role=role,
                source=Source(
                    id=source_id,
                    url="https://example.test/promotion",
                    source_type="web_page",
                    retrieved_at=now,
                    verified_at=now,
                ),
            )
            for role, source_id in zip(("primary", "claim"), source_ids, strict=True)
        ]
        session.add(promotion)
    try:
        yield factory, identity
    finally:
        with factory.begin() as session:
            session.execute(delete(Promotion).where(Promotion.id == identity))
            session.execute(delete(Source).where(Source.id.in_(source_ids)))
            session.execute(delete(Product).where(Product.manufacturer_id == manufacturer_id))
            session.execute(delete(Manufacturer).where(Manufacturer.id == manufacturer_id))


def test_committed_publication_and_repeated_activation(committed_graph):
    factory, identity = committed_graph
    operation = partial(promotion_transaction, factory)
    assert change_promotion_status(operation, identity, S.ACTIVE).changed
    with factory() as session:
        assert SqlAlchemyPromotionRepository(session).get_promotion(identity).status == S.ACTIVE
    assert not change_promotion_status(operation, identity, S.ACTIVE).changed


def test_parent_lock_serializes_edit_and_requires_revalidation(committed_graph):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from sqlalchemy import select

    from app.db.models import Promotion

    factory, identity = committed_graph
    attempted = Event()

    class ObservedRepository(SqlAlchemyPromotionRepository):
        def get_publication_snapshot_for_update(self, promotion_id):
            attempted.set()
            return super().get_publication_snapshot_for_update(promotion_id)

    @contextmanager
    def observed_transaction():
        with factory() as session, session.begin():
            yield ObservedRepository(session)

    with ThreadPoolExecutor(max_workers=1) as pool:
        with factory.begin() as editor:
            promotion = editor.scalar(
                select(Promotion).where(Promotion.id == identity).with_for_update()
            )
            future = pool.submit(change_promotion_status, observed_transaction, identity, S.ACTIVE)
            assert attempted.wait(10)
            promotion.claim_start_offset_days = promotion.claim_end_offset_days = None
        with pytest.raises(PromotionPublicationError) as error:
            future.result(timeout=10)
        assert "missing_claim_window" in {i.code for i in error.value.report.issues}
    with factory() as session:
        assert SqlAlchemyPromotionRepository(session).get_promotion(identity).status == S.REVIEW


def test_concurrent_activation_has_one_change(committed_graph):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    factory, identity = committed_graph
    read = Barrier(2)

    class SynchronizedRepository(SqlAlchemyPromotionRepository):
        def get_publication_snapshot_for_update(self, promotion_id):
            read.wait(timeout=10)
            return super().get_publication_snapshot_for_update(promotion_id)

    @contextmanager
    def synchronized_transaction():
        with factory() as session, session.begin():
            yield SynchronizedRepository(session)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(change_promotion_status, synchronized_transaction, identity, S.ACTIVE)
            for _ in range(2)
        ]
        results = [future.result(timeout=10) for future in futures]
    assert sorted(result.changed for result in results) == [False, True]
