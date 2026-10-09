from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from functools import partial
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.application.promotions import (
    PromotionConflict,
    PromotionNotFound,
    PromotionPersistenceError,
    change_promotion_status,
)
from app.db.models import Manufacturer, Promotion, PromotionSource, Source
from app.db.repositories.promotions import SqlAlchemyPromotionRepository, promotion_transaction
from app.domain.promotion_lifecycle import InvalidPromotionTransition
from app.domain.promotion_lifecycle import PromotionStatus as S
from app.domain.requirements import RequirementType
from tests.integration.test_core_promotion_schema import graph as complete_graph  # noqa: F401

pytestmark = pytest.mark.integration


@pytest.fixture
def graph(request):
    return request.getfixturevalue("complete_graph")


@contextmanager
def transaction(session):
    # Fixture owns the outer rollback; application commits a nested savepoint.
    with session.begin_nested():
        yield SqlAlchemyPromotionRepository(session)


def snapshot(session):
    from app.db.base import Base

    return {
        table.name: sorted((tuple(row) for row in session.execute(select(table))), key=repr)
        for table in Base.metadata.sorted_tables
    }


@pytest.mark.parametrize(
    "initial,target",
    [
        (S.ACTIVE, S.EXPIRED),
        (S.ACTIVE, S.ARCHIVED),
        (S.EXPIRED, S.ARCHIVED),
    ],
)
def test_retirement_preserves_entire_graph(db_session, graph, initial, target):
    graph.status = initial
    graph.claim_start_date = date(2026, 11, 1)
    graph.claim_end_date = date(2026, 11, 30)
    db_session.flush()
    identity = graph.id
    before = snapshot(db_session)
    statements = []

    def capture(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", capture)
    try:
        result = change_promotion_status(partial(transaction, db_session), identity, target)
        assert result.changed
        db_session.expunge_all()
        loaded = db_session.get(Promotion, identity)
        assert loaded.status == target
        assert loaded.manufacturer.products
        for variant in loaded.variants:
            assert variant.retailer is not None or variant.code == "variant-2"
            assert len(variant.product_links) == 2
            assert len(variant.benefits) == 3
            assert len(variant.requirements) == len(RequirementType)
            assert {row.requirement_type for row in variant.requirements} == set(RequirementType)
        assert len(loaded.variants) == 3
        assert all(link.source.verified_at is not None for link in loaded.source_links)
        after = snapshot(db_session)
        for table in before.keys() - {"promotions"}:
            assert after[table] == before[table]
        columns = list(Promotion.__table__.columns.keys())
        for column in columns:
            if column not in {"status", "updated_at"}:
                index = columns.index(column)
                assert after["promotions"][0][index] == before["promotions"][0][index]
        repository = SqlAlchemyPromotionRepository(db_session)
        assert repository.get_promotion(identity).status == target
        assert [p.id for p in repository.list_promotions([target])] == [identity]
        assert [p.id for p in repository.list_historical_promotions()] == (
            [identity] if target == S.EXPIRED else []
        )
        assert repository.list_active_promotions() == []
        timestamp = loaded.updated_at
        assert not change_promotion_status(
            partial(transaction, db_session), identity, target
        ).changed
        db_session.expire_all()
        assert db_session.get(Promotion, identity).updated_at == timestamp
    finally:
        event.remove(db_session.bind, "before_cursor_execute", capture)
    assert not any(s.lstrip().upper().startswith("DELETE") for s in statements)


def test_lookup_filters_order_and_no_read_time_expiration(db_session, graph):
    graph.created_at = datetime(2026, 10, 1, tzinfo=UTC)
    identities = {S.ACTIVE: graph.id}
    for index, status in enumerate(s for s in S if s != S.ACTIVE):
        promotion = Promotion(
            id=UUID(int=index + 1),
            manufacturer=graph.manufacturer,
            name=status.value,
            slug=status.value,
            status=status.value,
            created_at=datetime(2026, 10, 2, tzinfo=UTC) + timedelta(days=index // 2),
        )
        db_session.add(promotion)
        identities[status] = promotion.id
    db_session.flush()
    repository = SqlAlchemyPromotionRepository(db_session)
    for status, identity in identities.items():
        assert repository.get_promotion(identity).status == status
    assert repository.get_promotion(uuid4()) is None
    all_rows = repository.list_promotions()
    assert len(all_rows) == 6
    assert all_rows == sorted(all_rows, key=lambda p: (-p.created_at.timestamp(), p.id))
    assert {p.status for p in repository.list_promotions([S.REVIEW, S.EXPIRED])} == {
        S.REVIEW,
        S.EXPIRED,
    }
    assert repository.list_promotions([]) == []
    assert [p.status for p in repository.list_active_promotions()] == [S.ACTIVE]
    assert {p.status for p in repository.list_historical_promotions()} == {S.EXPIRED}
    assert [p.status for p in repository.list_historical_promotions([S.EXPIRED])] == [S.EXPIRED]
    assert repository.list_historical_promotions([]) == []
    assert [p.id for p in repository.list_promotions([S.ARCHIVED])] == [identities[S.ARCHIVED]]
    for unsupported in (S.REVIEW, S.ARCHIVED):
        with pytest.raises(ValueError, match="require expired"):
            repository.list_historical_promotions([unsupported])
    with pytest.raises(ValueError):
        repository.list_promotions(["published"])
    db_session.expire_all()
    assert db_session.get(Promotion, graph.id).status == S.ACTIVE


def test_invalid_and_missing_do_not_write(db_session, graph):
    before = snapshot(db_session)
    with pytest.raises(InvalidPromotionTransition):
        change_promotion_status(partial(transaction, db_session), graph.id, S.REVIEW)
    with pytest.raises(PromotionNotFound):
        change_promotion_status(partial(transaction, db_session), uuid4(), S.EXPIRED)
    assert snapshot(db_session) == before


@pytest.mark.parametrize("winner", [S.EXPIRED, S.ARCHIVED])
def test_stale_application_write_real_postgres(postgres_engine, migrated_test_database, winner):
    factory = sessionmaker(postgres_engine)
    identity, manufacturer_id = uuid4(), uuid4()
    with factory.begin() as session:
        session.add(Manufacturer(id=manufacturer_id, name="Concurrent", slug=str(manufacturer_id)))
        session.add(
            Promotion(
                id=identity,
                manufacturer_id=manufacturer_id,
                name="Concurrent",
                slug=str(identity),
                status=S.ACTIVE,
            )
        )
    try:

        class InterleavedRepository(SqlAlchemyPromotionRepository):
            def update_status(self, promotion_id, expected, target):
                # Two real transactions: commit a competing update after this service's read.
                with promotion_transaction(factory) as competitor:
                    assert competitor.update_status(promotion_id, S.ACTIVE, winner)
                return super().update_status(promotion_id, expected, target)

        @contextmanager
        def interleaved():
            with factory() as session, session.begin():
                yield InterleavedRepository(session)

        if winner == S.EXPIRED:
            assert not change_promotion_status(interleaved, identity, S.EXPIRED).changed
        else:
            with pytest.raises(PromotionConflict):
                change_promotion_status(interleaved, identity, S.EXPIRED)
        with promotion_transaction(factory) as repository:
            assert repository.get_promotion(identity).status == winner
    finally:
        # Explicit test cleanup is separate from lifecycle behaviour.
        with factory.begin() as session:
            session.delete(session.get(Promotion, identity))
            session.delete(session.get(Manufacturer, manufacturer_id))


@pytest.mark.parametrize("failure_stage", ["update", "commit", "query"])
def test_database_failure_boundary_and_rollback(db_session, graph, failure_stage):
    identity = graph.id
    before = snapshot(db_session)

    def fail(*args, **kwargs):
        raise OperationalError("private SQL", {}, Exception("private detail"))

    if failure_stage == "commit":

        def factory():
            return Session(bind=db_session.connection(), join_transaction_mode="create_savepoint")

        event.listen(Session, "before_commit", fail)
        try:
            with pytest.raises(PromotionPersistenceError, match="transaction failed"):
                change_promotion_status(
                    partial(promotion_transaction, factory), identity, S.EXPIRED
                )
        finally:
            event.remove(Session, "before_commit", fail)
    else:
        event.listen(db_session.bind, "before_cursor_execute", fail)
        try:
            repository = SqlAlchemyPromotionRepository(db_session)
            with pytest.raises(PromotionPersistenceError) as error:
                if failure_stage == "update":
                    with transaction(db_session) as repository:
                        repository.update_status(identity, S.ACTIVE, S.EXPIRED)
                else:
                    repository.list_promotions()
            assert "private" not in str(error.value)
        finally:
            event.remove(db_session.bind, "before_cursor_execute", fail)
    db_session.expire_all()
    assert snapshot(db_session) == before


def test_application_commit_is_visible_in_new_session(postgres_engine, migrated_test_database):
    factory = sessionmaker(postgres_engine)
    identity, manufacturer_id = uuid4(), uuid4()
    with factory.begin() as session:
        session.add(Manufacturer(id=manufacturer_id, name="Committed", slug=str(manufacturer_id)))
        session.add(
            Promotion(
                id=identity,
                manufacturer_id=manufacturer_id,
                name="Committed",
                slug=str(identity),
                status=S.REVIEW,
                purchase_start_date=date(2026, 10, 1),
                claim_start_offset_days=0,
                claim_end_offset_days=30,
            )
        )
    with factory.begin() as session:
        for role in ("primary", "claim"):
            session.add(
                PromotionSource(
                    promotion_id=identity,
                    role=role,
                    source=Source(
                        url="https://example.test/promo",
                        source_type="web_page",
                        retrieved_at=datetime(2026, 10, 6, tzinfo=UTC),
                        verified_at=datetime(2026, 10, 6, tzinfo=UTC),
                    ),
                )
            )
    from app.db.models import Benefit, Product, PromotionVariant, PromotionVariantProduct

    with factory.begin() as session:
        product = Product(manufacturer_id=manufacturer_id, name="Product", slug="product")
        variant = PromotionVariant(promotion_id=identity, code="all")
        variant.product_links = [PromotionVariantProduct(product=product)]
        variant.benefits = [Benefit(benefit_type="free_gift", name="Gift")]
        session.add(variant)
    try:
        transaction_factory = partial(promotion_transaction, factory)
        assert change_promotion_status(transaction_factory, identity, S.ACTIVE).changed
        with promotion_transaction(factory) as repository:
            assert repository.get_promotion(identity).status == S.ACTIVE
        with pytest.raises(InvalidPromotionTransition):
            change_promotion_status(transaction_factory, identity, S.REVIEW)
        with promotion_transaction(factory) as repository:
            assert repository.get_promotion(identity).status == S.ACTIVE
    finally:
        with factory.begin() as session:
            source_rows = list(
                session.scalars(
                    select(Source)
                    .join(PromotionSource)
                    .where(PromotionSource.promotion_id == identity)
                )
            )
            session.delete(session.get(Promotion, identity))
            session.flush()
            for source in source_rows:
                session.delete(source)
            for product in session.scalars(
                select(Product).where(Product.manufacturer_id == manufacturer_id)
            ):
                session.delete(product)
            session.flush()
            session.delete(session.get(Manufacturer, manufacturer_id))


@pytest.mark.parametrize("initial", [S.DISCOVERED, S.EXTRACTED, S.REVIEW])
def test_archived_candidate_is_retained_but_not_historical_published(db_session, initial):
    candidate = Promotion(
        manufacturer=Manufacturer(name="Candidate", slug="candidate"),
        name="Abandoned candidate",
        slug="abandoned",
        status=initial,
    )
    db_session.add(candidate)
    db_session.flush()
    identity = candidate.id
    assert change_promotion_status(partial(transaction, db_session), identity, S.ARCHIVED).changed
    db_session.expunge_all()
    repository = SqlAlchemyPromotionRepository(db_session)
    assert repository.get_promotion(identity).status == S.ARCHIVED
    assert [p.id for p in repository.list_promotions([S.ARCHIVED])] == [identity]
    assert repository.list_historical_promotions() == []
    assert repository.list_active_promotions() == []
