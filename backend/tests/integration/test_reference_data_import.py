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
        preview = command("--plan", "--preview-promotions")
        assert preview["counts"]["promotion"]["create"] == 5
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


def test_cross_manufacturer_model_is_independent_and_replay_preserves_it(db_session):
    other = Manufacturer(name="Unrelated maker", slug="unrelated-maker")
    db_session.add(other)
    db_session.flush()
    unrelated = Product(
        manufacturer_id=other.id, name="Other SM-R640", slug="other-model", model_number="SM-R640"
    )
    db_session.add(unrelated)
    db_session.flush()
    original = (
        unrelated.id,
        unrelated.manufacturer_id,
        unrelated.name,
        unrelated.slug,
        unrelated.model_number,
        unrelated.created_at,
        unrelated.updated_at,
    )
    assert any(
        e.kind == "product" and e.key == "SM-R640" and e.action == "create"
        for e in run(db_session, apply=False).entities
    )
    run(db_session)
    assert (
        len(list(db_session.scalars(select(Product).where(Product.model_number == "SM-R640")))) == 2
    )
    after = snapshot(db_session)
    assert run(db_session).no_op
    assert snapshot(db_session) == after
    db_session.refresh(unrelated)
    assert (
        unrelated.id,
        unrelated.manufacturer_id,
        unrelated.name,
        unrelated.slug,
        unrelated.model_number,
        unrelated.created_at,
        unrelated.updated_at,
    ) == original


@pytest.mark.parametrize(
    "field,value", [("name", "Wrong display name"), ("model_number", "WRONG-MODEL")]
)
def test_conflicting_canonical_product_facts_rejected(db_session, field, value):
    run(db_session)
    row = db_session.scalar(select(Product).where(Product.model_number == "SM-R640"))
    setattr(row, field, value)
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(ReferenceDataConflict, match="Conflicting product"):
        run(db_session)
    assert snapshot(db_session) == before


def test_promotion_preview_is_read_only_for_new_and_existing_graphs(db_session):
    from sqlalchemy import event

    statements = []
    connection = db_session.connection()

    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.strip().upper())

    def preview():
        event.listen(connection, "before_cursor_execute", record)
        try:
            return import_reference_data(
                SqlAlchemyReferenceDataRepository(db_session),
                load_dataset(),
                preview_promotions=True,
            )
        finally:
            event.remove(connection, "before_cursor_execute", record)

    before = snapshot(db_session)
    report = preview()
    assert [e.action for e in report.entities if e.kind == "promotion"] == ["create"] * 5
    assert snapshot(db_session) == before
    assert not db_session.new and not db_session.dirty and not db_session.deleted
    assert not any(
        s.startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT")) or "FOR UPDATE" in s
        for s in statements
    )
    run(db_session, stage=True)
    before = snapshot(db_session)
    statements.clear()
    report = preview()
    assert [e.action for e in report.entities if e.kind == "promotion"] == ["reuse"] * 5
    assert snapshot(db_session) == before
    assert not any(
        s.startswith(("INSERT", "UPDATE", "DELETE", "SAVEPOINT")) or "FOR UPDATE" in s
        for s in statements
    )


@pytest.mark.parametrize(
    "mismatch", ["reward", "variant", "requirement", "source", "lifecycle", "product", "retailer"]
)
def test_conflicting_graph_preflight_prevents_catalogue_writes(db_session, mismatch):
    from sqlalchemy import event

    from app.db.reference.sony import construct_reference

    promotion = construct_reference(db_session)
    variant = promotion.variants[0]
    if mismatch == "reward":
        variant.benefits[0].reward.fixed_amount = 1
    elif mismatch == "variant":
        variant.code = "conflicting-code"
    elif mismatch == "requirement":
        variant.requirements[0].description = "Conflicting requirement"
    elif mismatch == "source":
        promotion.source_links[0].source.title = "Conflicting evidence"
    elif mismatch == "lifecycle":
        promotion.status = "extracted"
    elif mismatch == "product":
        db_session.delete(variant.product_links[0])
    elif mismatch == "retailer":
        variant.retailer_id = None
    db_session.flush()
    before = snapshot(db_session)
    statements = []
    connection = db_session.connection()

    def record(_connection, _cursor, statement, _parameters, _context, _executemany):
        statements.append(statement.strip().upper())

    event.listen(connection, "before_cursor_execute", record)
    try:
        with pytest.raises(ReferenceDataConflict, match="Sony"):
            run(db_session, stage=True)
    finally:
        event.remove(connection, "before_cursor_execute", record)
    assert snapshot(db_session) == before
    assert not any(s.startswith(("INSERT", "UPDATE", "DELETE")) for s in statements)
    # Catalogue operations remain independent of the incompatible promotion graph.
    run(db_session)
    assert len(list(db_session.scalars(select(Manufacturer)))) == 5


def test_database_failure_during_stage_rolls_back_catalogue(db_session, monkeypatch):
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    before = snapshot(db_session)
    original = SqlAlchemyReferenceDataRepository.stage

    def fail(repository, _dataset):
        repository.session.execute(text("SELECT 1 / 0"))

    monkeypatch.setattr(SqlAlchemyReferenceDataRepository, "stage", fail)
    with pytest.raises(DBAPIError), db_session.begin_nested():
        run(db_session, stage=True)
    assert snapshot(db_session) == before
    monkeypatch.setattr(SqlAlchemyReferenceDataRepository, "stage", original)
    assert run(db_session, stage=True).staged_promotions == 5
