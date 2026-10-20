"""Real migrated PostgreSQL catalogue, atomicity and replay guarantees."""

import pytest
from sqlalchemy import select

from app.application.reference_data_import import (
    ReferenceDataConflict,
    import_reference_data,
    load_dataset,
)
from app.db.base import Base
from app.db.models import Manufacturer, Product, Promotion, Retailer, RetailerAlias
from app.db.repositories.reference_data_import import SqlAlchemyReferenceDataRepository

pytestmark = pytest.mark.integration


def snapshot(session):
    return {
        table.name: tuple(session.execute(select(table)).all())
        for table in Base.metadata.sorted_tables
    }


def run(session, *, apply=True, stage=False):
    repository = SqlAlchemyReferenceDataRepository(session)
    if apply:
        repository.lock()
    return import_reference_data(repository, load_dataset(), apply=apply, stage_promotions=stage)


def test_plan_apply_replay_exact_catalogue(db_session):
    before = snapshot(db_session)
    first_plan = run(db_session, apply=False)
    assert snapshot(db_session) == before
    assert len(first_plan.entities) == 15
    run(db_session)
    assert len(list(db_session.scalars(select(Manufacturer)))) == 5
    assert len(list(db_session.scalars(select(Retailer)))) == 4
    assert len(list(db_session.scalars(select(Product)))) == 5
    assert list(db_session.scalars(select(Promotion))) == []
    assert len(list(db_session.scalars(select(RetailerAlias)))) == 1
    after = snapshot(db_session)
    replay = run(db_session)
    assert all(entity.action == "reuse" for entity in replay.entities)
    assert snapshot(db_session) == after


def test_conflict_preflight_inserts_nothing(db_session):
    db_session.add(Manufacturer(name="Sony", slug="wrong-sony"))
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(ReferenceDataConflict, match="facts"):
        run(db_session)
    assert snapshot(db_session) == before


def test_alias_collision_rejected(db_session):
    other = Retailer(name="Other", slug="other")
    db_session.add(other)
    db_session.flush()
    db_session.add(RetailerAlias(retailer_id=other.id, alias="Currys - UK"))
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(ReferenceDataConflict, match="alias owner"):
        run(db_session)
    assert snapshot(db_session) == before


def test_stage_and_replay_preserve_complete_graph(db_session):
    report = run(db_session, stage=True)
    assert report.staged_promotions == 5
    assert set(db_session.scalars(select(Promotion.status))) == {"review"}
    before = snapshot(db_session)
    report = run(db_session, stage=True)
    assert report.staged_promotions == 0 and report.reused_promotions == 5
    assert snapshot(db_session) == before


def test_mid_run_failure_rolls_back_and_retry_succeeds(db_session, monkeypatch):
    before = snapshot(db_session)
    original = SqlAlchemyReferenceDataRepository.stage

    def fail(self, dataset):
        raise ReferenceDataConflict("forced staging failure")

    monkeypatch.setattr(SqlAlchemyReferenceDataRepository, "stage", fail)
    with pytest.raises(ReferenceDataConflict), db_session.begin_nested():
        run(db_session, stage=True)
    assert snapshot(db_session) == before
    monkeypatch.setattr(SqlAlchemyReferenceDataRepository, "stage", original)
    assert run(db_session, stage=True).staged_promotions == 5


def test_compatible_rows_and_unrelated_data_preserved(db_session):
    db_session.add_all(
        [Manufacturer(name="Samsung", slug="samsung"), Retailer(name="Unrelated", slug="unrelated")]
    )
    db_session.flush()
    samsung = db_session.scalar(select(Manufacturer).where(Manufacturer.slug == "samsung"))
    before = (samsung.id, samsung.created_at, samsung.updated_at)
    run(db_session)
    assert (samsung.id, samsung.created_at, samsung.updated_at) == before
    assert db_session.scalar(select(Retailer).where(Retailer.slug == "unrelated"))


def test_duplicate_normalized_models_fail_without_changes(db_session):
    run(db_session)
    product = db_session.scalar(select(Product).where(Product.model_number == "SM-R640"))
    db_session.add(
        Product(
            manufacturer_id=product.manufacturer_id,
            name="Duplicate",
            slug="duplicate-model",
            model_number="ＳＭ-Ｒ６４０",
        )
    )
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(ReferenceDataConflict, match="Ambiguous"):
        run(db_session)
    assert snapshot(db_session) == before


def test_published_historical_archived_graphs_replayed_unchanged(db_session):
    from functools import partial

    from app.application.promotions import change_promotion_status
    from app.domain.promotion_lifecycle import PromotionStatus
    from tests.integration.test_promotion_lifecycle import transaction

    run(db_session, stage=True)
    promotions = list(db_session.scalars(select(Promotion).order_by(Promotion.slug)))
    operation = partial(transaction, db_session)
    for promotion, target in zip(promotions, ["active", "expired", "archived"], strict=False):
        change_promotion_status(operation, promotion.id, PromotionStatus.ACTIVE)
        if target != "active":
            change_promotion_status(operation, promotion.id, PromotionStatus(target))
    before = snapshot(db_session)
    run(db_session, stage=True)
    assert snapshot(db_session) == before


def test_concurrent_operator_applies_reconcile(postgres_engine, migrated_test_database):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from sqlalchemy.orm import sessionmaker

    from app.db.models import Source
    from tests.integration.test_sony_reference_promotion import delete_owned_rows

    factory = sessionmaker(postgres_engine)
    kinds = (Promotion, Source, Product, Retailer, Manufacturer)
    with factory() as session:
        before = {kind: set(session.scalars(select(kind.id))) for kind in kinds}
        aliases = set(
            session.execute(select(RetailerAlias.retailer_id, RetailerAlias.normalised_alias))
        )
    barrier = Barrier(2)

    def apply():
        barrier.wait(timeout=5)
        with factory.begin() as session:
            return run(session, stage=True)

    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            results = list(workers.map(lambda _: apply(), range(2)))
        assert sorted(r.staged_promotions for r in results) == [0, 5]
        with factory() as session:
            assert len(set(session.scalars(select(Product.id))) - before[Product]) == 5
            assert len(set(session.scalars(select(Promotion.id))) - before[Promotion]) == 5
    finally:
        with factory.begin() as session:
            owned = {kind: set(session.scalars(select(kind.id))) - before[kind] for kind in kinds}
            owned[RetailerAlias] = (
                set(
                    session.execute(
                        select(RetailerAlias.retailer_id, RetailerAlias.normalised_alias)
                    )
                )
                - aliases
            )
            delete_owned_rows(session, owned)


def test_cli_default_plan_apply_and_staged_replay(
    postgres_engine, migrated_test_database, database_url
):
    import json
    import os
    import subprocess
    import sys

    from sqlalchemy.orm import sessionmaker

    from app.db.models import Source
    from tests.integration.test_sony_reference_promotion import delete_owned_rows

    factory = sessionmaker(postgres_engine)
    kinds = (Promotion, Source, Product, Retailer, Manufacturer)
    with factory() as session:
        before = {kind: set(session.scalars(select(kind.id))) for kind in kinds}
        aliases = set(
            session.execute(select(RetailerAlias.retailer_id, RetailerAlias.normalised_alias))
        )
        original = snapshot(session)
    environment = {**os.environ, "APP_ENV": "test", "DATABASE_URL": database_url}

    def command(*args):
        result = subprocess.run(
            [sys.executable, "-m", "app.cli.seed_reference_data", *args],
            env=environment,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        lines = [json.loads(line) for line in result.stdout.splitlines()]
        assert set(lines[0]["target"]) == {"host", "port", "database"}
        return lines[-1]

    try:
        assert command()["mode"] == "plan"
        with factory() as session:
            assert snapshot(session) == original
        assert command("--apply")["counts"]["product"]["create"] == 5
        first = command("--apply", "--stage-promotions")
        assert first["staged_promotions"] == 5 and first["published_promotions"] == 0
        with factory() as session:
            staged = snapshot(session)
        second = command("--apply", "--stage-promotions")
        assert second["no_op"] is True and second["staged_promotions"] == 0
        with factory() as session:
            assert snapshot(session) == staged
    finally:
        with factory.begin() as session:
            owned = {kind: set(session.scalars(select(kind.id))) - before[kind] for kind in kinds}
            owned[RetailerAlias] = (
                set(
                    session.execute(
                        select(RetailerAlias.retailer_id, RetailerAlias.normalised_alias)
                    )
                )
                - aliases
            )
            delete_owned_rows(session, owned)
