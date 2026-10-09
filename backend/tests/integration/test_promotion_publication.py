from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from functools import partial

import pytest
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.application.promotions import (
    PromotionPersistenceError,
    PromotionPublicationError,
    change_promotion_status,
)
from app.db.models import (
    BenefitProductRewardValue,
    BenefitReward,
    Manufacturer,
    Product,
    PromotionSource,
    PromotionVariantProduct,
    Source,
)
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
            purchase_end_date=date(2026, 10, 31),
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


def assert_rejected_without_changes(session, graph, code):
    session.flush()
    session.expire_all()
    before = snapshot(session)
    with pytest.raises(PromotionPublicationError) as error:
        change_promotion_status(partial(transaction, session), graph.id, S.ACTIVE)
    assert code in {issue.code for issue in error.value.report.issues}
    assert snapshot(session) == before
    assert session.get(type(graph), graph.id).status == S.REVIEW
    return error.value.report


@pytest.mark.parametrize("mapping", ["complete", "missing", "extra"])
def test_product_specific_reward_publication(db_session, graph, mapping):
    variant = graph.variants[0]
    reward = next(b.reward for b in variant.benefits if b.benefit_type == "cashback")
    reward.reward_type, reward.fixed_amount = "product_specific", None
    products = [link.product for link in variant.product_links]
    if mapping == "missing":
        products = products[:-1]
    if mapping == "extra":
        products.append(Product(manufacturer=graph.manufacturer, name="Extra", slug="extra"))
    reward.product_values = [
        BenefitProductRewardValue(product=p, amount=Decimal("25.00")) for p in products
    ]
    db_session.flush()
    if mapping == "complete":
        assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed
        db_session.expire_all()
        assert db_session.get(type(graph), graph.id).status == S.ACTIVE
    else:
        assert_rejected_without_changes(db_session, graph, "product_reward_coverage_mismatch")
        # Correcting the existing rows preserves candidate identity and allows retry.
        if mapping == "missing":
            reward.product_values.append(
                BenefitProductRewardValue(
                    product=variant.product_links[-1].product, amount=Decimal("25.00")
                )
            )
        else:
            db_session.delete(next(v for v in reward.product_values if v.product.slug == "extra"))
        db_session.flush()
        if mapping == "extra":
            # The deleted row may remain in this already-loaded collection until expired.
            db_session.expire(reward, ["product_values"])
        assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed


def test_duplicate_product_reward_rejected_by_postgres(db_session, graph):
    variant = graph.variants[0]
    reward = next(b.reward for b in variant.benefits if b.benefit_type == "cashback")
    reward.reward_type, reward.fixed_amount = "product_specific", None
    reward.product_values = [
        BenefitProductRewardValue(product=link.product, amount=Decimal("25.00"))
        for link in variant.product_links
    ]
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(
            BenefitProductRewardValue(
                benefit_id=reward.benefit_id,
                product_id=variant.product_links[0].product_id,
                amount=Decimal("99.00"),
            )
        )
        db_session.flush()
    assert snapshot(db_session) == before
    assert graph.status == S.REVIEW
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed


@pytest.mark.parametrize("role", ["primary", "claim"])
def test_duplicate_source_role_blocks_publication(db_session, graph, role):
    source = next(link.source for link in graph.source_links if link.role == role)
    graph.source_links.append(
        PromotionSource(
            role=role,
            source=Source(
                url=source.url,
                source_type=source.source_type,
                retrieved_at=source.retrieved_at,
                verified_at=source.verified_at,
            ),
        )
    )
    assert_rejected_without_changes(db_session, graph, f"ambiguous_{role}_source")


@pytest.mark.parametrize("role", ["primary", "claim"])
def test_source_verification_correction_allows_retry(db_session, graph, role):
    source = next(link.source for link in graph.source_links if link.role == role)
    verified = source.verified_at
    source.verified_at = None
    assert_rejected_without_changes(db_session, graph, f"{role}_source_unverified")
    source.verified_at = verified
    db_session.flush()
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed
    db_session.expire_all()
    assert db_session.get(type(graph), graph.id).status == S.ACTIVE


@pytest.mark.parametrize("kind", ["fixed", "relative", "delayed", "open_fixed", "open_zero"])
def test_supported_claim_windows_publish(db_session, graph, kind):
    if kind in {"fixed", "open_fixed"}:
        graph.claim_start_offset_days = graph.claim_end_offset_days = None
        graph.claim_start_date, graph.claim_end_date = date(2026, 11, 1), date(2026, 11, 30)
    if kind == "delayed":
        graph.claim_start_offset_days, graph.claim_end_offset_days = 30, 60
    if kind in {"open_fixed", "open_zero"}:
        graph.purchase_end_date = None
    if kind == "open_zero":
        graph.claim_start_offset_days = graph.claim_end_offset_days = 0
    db_session.flush()
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed
    db_session.expire_all()
    assert db_session.get(type(graph), graph.id).status == S.ACTIVE


@pytest.mark.parametrize("kind", ["missing", "huge", "near_max", "open_positive"])
def test_unrepresentable_or_incomplete_claim_window_rejects_and_retries(db_session, graph, kind):
    if kind == "missing":
        graph.claim_start_offset_days = graph.claim_end_offset_days = None
    elif kind == "huge":
        graph.claim_end_offset_days = 3652058
    elif kind == "near_max":
        graph.purchase_end_date = date.max
        graph.claim_end_offset_days = 1
    else:
        graph.purchase_end_date = None
    code = "missing_claim_window" if kind == "missing" else "invalid_claim_window"
    report = assert_rejected_without_changes(db_session, graph, code)
    assert any(i.code == code and i.path == "/promotion/claim_window" for i in report.issues)
    graph.claim_start_offset_days = graph.claim_end_offset_days = None
    graph.claim_start_date, graph.claim_end_date = date(2026, 11, 1), date(2026, 11, 30)
    db_session.flush()
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed


@pytest.mark.parametrize("kind", ["partial_fixed", "partial_relative", "reversed", "mixed"])
def test_invalid_claim_shapes_rejected_by_postgres(db_session, graph, kind):
    before = snapshot(db_session)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        if kind == "partial_fixed":
            graph.claim_start_offset_days = graph.claim_end_offset_days = None
            graph.claim_start_date = date(2026, 11, 1)
        elif kind == "partial_relative":
            graph.claim_end_offset_days = None
        elif kind == "reversed":
            graph.claim_start_offset_days = 31
        else:
            graph.claim_start_date, graph.claim_end_date = date(2026, 11, 1), date(2026, 11, 30)
        db_session.flush()
    assert snapshot(db_session) == before
    assert graph.status == S.REVIEW


def test_publication_visibility_and_historical_retirement(db_session, graph):
    variant = graph.variants[0]
    product_id = variant.product_links[0].product_id
    repository = SqlAlchemyPromotionRepository(db_session)

    def matches():
        return repository.find_promotion_candidates(
            manufacturer_id=graph.manufacturer_id,
            retailer_id=variant.retailer_id,
            product_id=product_id,
            purchase_date=date(2026, 10, 1),
        )

    graph.claim_start_offset_days = graph.claim_end_offset_days = None
    assert_rejected_without_changes(db_session, graph, "missing_claim_window")
    assert matches() == ()
    graph.claim_start_offset_days, graph.claim_end_offset_days = 0, 30
    db_session.flush()
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.ACTIVE).changed
    assert {c.promotion_id for c in matches()} == {graph.id}
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.EXPIRED).changed
    assert {c.promotion_id for c in matches()} == {graph.id}
    assert change_promotion_status(partial(transaction, db_session), graph.id, S.ARCHIVED).changed
    assert matches() == ()


@pytest.mark.parametrize("status", [S.DISCOVERED, S.EXTRACTED, S.REVIEW, S.ARCHIVED])
def test_unpublished_states_remain_excluded(db_session, graph, status):
    graph.status = status
    db_session.flush()
    variant = graph.variants[0]
    assert (
        SqlAlchemyPromotionRepository(db_session).find_promotion_candidates(
            manufacturer_id=graph.manufacturer_id,
            retailer_id=variant.retailer_id,
            product_id=variant.product_links[0].product_id,
            purchase_date=date(2026, 10, 1),
        )
        == ()
    )


@pytest.mark.parametrize("status", [S.ACTIVE, S.EXPIRED])
def test_existing_published_graph_is_queryable_without_revalidation(db_session, graph, status):
    graph.status = status
    graph.claim_start_offset_days = graph.claim_end_offset_days = None
    db_session.flush()
    before = snapshot(db_session)
    variant = graph.variants[0]
    candidates = SqlAlchemyPromotionRepository(db_session).find_promotion_candidates(
        manufacturer_id=graph.manufacturer_id,
        retailer_id=variant.retailer_id,
        product_id=variant.product_links[0].product_id,
        purchase_date=date(2026, 10, 1),
    )
    assert {candidate.promotion_id for candidate in candidates} == {graph.id}
    assert snapshot(db_session) == before
