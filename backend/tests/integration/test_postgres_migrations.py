import os
import re
import subprocess
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import CheckConstraint, Date, Integer, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import models  # noqa: F401
from app.db.base import Base
from app.db.models import Manufacturer, Promotion, PromotionVariant, Requirement
from app.domain.requirements import RequirementType

pytestmark = pytest.mark.integration


def test_fresh_postgres_connectivity_and_migration_head(
    postgres_engine: Engine,
    migrated_test_database: None,
) -> None:
    with postgres_engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert set(Base.metadata.tables) <= set(inspect(postgres_engine).get_table_names())
    assert revision == "0006_promotion_requirements"
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = postgres_engine.url.render_as_string(
        hide_password=False
    )
    subprocess.run(
        ["alembic", "downgrade", "0003_identity_normalisation"],
        check=True,
        env=migration_environment,
    )
    with postgres_engine.connect() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0003_identity_normalisation"
        )
    assert not {"claim_start_date", "claim_end_date"} & {
        column["name"] for column in inspect(postgres_engine).get_columns("promotions")
    }
    manufacturer_id, promotion_id, variant_id, source_id = (uuid4() for _ in range(4))
    with postgres_engine.begin() as connection:
        connection.execute(
            text("INSERT INTO manufacturers (id, name, slug) VALUES (:id, 'Legacy', 'legacy')"),
            {"id": manufacturer_id},
        )
        connection.execute(
            text(
                "INSERT INTO promotions (id, manufacturer_id, name, slug, status, "
                "purchase_start_date, purchase_end_date) "
                "VALUES (:id, :manufacturer, 'Legacy', 'legacy', 'expired', "
                "'2026-10-01', '2026-10-31')"
            ),
            {"id": promotion_id, "manufacturer": manufacturer_id},
        )
        connection.execute(
            text(
                "INSERT INTO promotion_variants (id, promotion_id, code) "
                "VALUES (:id, :promotion, 'legacy')"
            ),
            {"id": variant_id, "promotion": promotion_id},
        )
        connection.execute(
            text(
                "INSERT INTO sources (id, url, source_type, retrieved_at, verified_at) "
                "VALUES (:id, 'https://example.test/legacy', 'web_page', "
                "'2026-10-01T00:00:00Z', '2026-10-02T00:00:00Z')"
            ),
            {"id": source_id},
        )
        connection.execute(
            text(
                "INSERT INTO promotion_sources (promotion_id, source_id, role) "
                "VALUES (:promotion, :source, 'primary')"
            ),
            {"promotion": promotion_id, "source": source_id},
        )
        before = (
            connection.execute(
                text("SELECT * FROM promotions WHERE id = :id"), {"id": promotion_id}
            )
            .mappings()
            .one()
        )
        source_before = (
            connection.execute(text("SELECT * FROM sources WHERE id = :id"), {"id": source_id})
            .mappings()
            .one()
        )
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=migration_environment)
    with postgres_engine.connect() as connection:
        after = dict(
            connection.execute(
                text("SELECT * FROM promotions WHERE id = :id"), {"id": promotion_id}
            )
            .mappings()
            .one()
        )
        assert after.pop("claim_start_offset_days") is None
        assert after.pop("claim_end_offset_days") is None
        assert after.pop("claim_start_date") is None
        assert after.pop("claim_end_date") is None
        assert after == dict(before)
        assert (
            connection.execute(text("SELECT * FROM sources WHERE id = :id"), {"id": source_id})
            .mappings()
            .one()
            == source_before
        )
        assert (
            connection.execute(
                text("SELECT promotion_id FROM promotion_variants WHERE id = :id"),
                {"id": variant_id},
            ).scalar_one()
            == promotion_id
        )
        assert connection.execute(
            text("SELECT source_id, role FROM promotion_sources WHERE promotion_id = :id"),
            {"id": promotion_id},
        ).one() == (source_id, "primary")
        context = MigrationContext.configure(
            connection,
            opts={
                "include_object": lambda obj, name, kind, reflected, other: (
                    name != "test_session_isolation_probe"
                )
            },
        )
        assert compare_metadata(context, Base.metadata) == []
    columns = {
        column["name"]: column for column in inspect(postgres_engine).get_columns("promotions")
    }
    for name in ("claim_start_date", "claim_end_date"):
        assert isinstance(columns[name]["type"], Date)
        assert columns[name]["nullable"]
        assert columns[name]["default"] is None
    assert {"ck_promotions_claim_dates_complete", "ck_promotions_claim_dates"} <= {
        constraint["name"]
        for constraint in inspect(postgres_engine).get_check_constraints("promotions")
    }
    assert all(
        not {"claim_start_date", "claim_end_date"} & set(index["column_names"])
        for index in inspect(postgres_engine).get_indexes("promotions")
    )
    # Also preserve the previous identity-schema and core-schema downgrade coverage.
    subprocess.run(
        ["alembic", "downgrade", "0002_core_promotion_schema"],
        check=True,
        env=migration_environment,
    )
    with postgres_engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0002_core_promotion_schema"
        )
    tables = set(inspect(postgres_engine).get_table_names())
    assert {
        "manufacturers",
        "products",
        "retailers",
        "promotions",
        "sources",
        "promotion_sources",
    } <= tables
    assert (
        not {
            "manufacturer_aliases",
            "product_model_aliases",
            "retailer_aliases",
            "retailer_product_skus",
            "retailer_groups",
            "retailer_group_aliases",
            "retailer_group_members",
        }
        & tables
    )
    assert "test_session_isolation_probe" in inspect(postgres_engine).get_table_names()
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=migration_environment)
    with postgres_engine.connect() as connection:
        final_revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert revision == "0006_promotion_requirements"
    assert final_revision == "0006_promotion_requirements"
    assert set(Base.metadata.tables) <= set(inspect(postgres_engine).get_table_names())

    # Retain the original core-schema downgrade coverage as well as the relative-window round trip.
    subprocess.run(
        ["alembic", "downgrade", "0001_initial_baseline"],
        check=True,
        env=migration_environment,
    )
    assert not set(Base.metadata.tables) & set(inspect(postgres_engine).get_table_names())
    assert "test_session_isolation_probe" in inspect(postgres_engine).get_table_names()
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=migration_environment)
    with postgres_engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0006_promotion_requirements"
        )
    assert set(Base.metadata.tables) <= set(inspect(postgres_engine).get_table_names())


def test_relative_upgrade_preserves_fixed_and_absent_windows(
    postgres_engine: Engine, migrated_test_database: None
) -> None:
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = postgres_engine.url.render_as_string(
        hide_password=False
    )
    subprocess.run(
        ["alembic", "downgrade", "0004_fixed_claim_windows"], check=True, env=migration_environment
    )
    inspector = inspect(postgres_engine)
    offsets = {"claim_start_offset_days", "claim_end_offset_days"}
    fixed = {"claim_start_date", "claim_end_date"}
    columns = {column["name"] for column in inspector.get_columns("promotions")}
    assert not offsets & columns
    assert fixed <= columns
    manufacturer_id, absent_id, fixed_id = (uuid4() for _ in range(3))
    with postgres_engine.begin() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0004_fixed_claim_windows"
        )
        connection.execute(
            text("INSERT INTO manufacturers (id, name, slug) VALUES (:id, 'Relative', 'relative')"),
            {"id": manufacturer_id},
        )
        connection.execute(
            text(
                "INSERT INTO promotions (id, manufacturer_id, name, slug, status, "
                "claim_start_date, claim_end_date) VALUES "
                "(:absent, :manufacturer, 'Absent', 'absent', 'review', NULL, NULL), "
                "(:fixed, :manufacturer, 'Fixed', 'fixed', 'expired', '2026-11-01', '2026-11-30')"
            ),
            {"absent": absent_id, "fixed": fixed_id, "manufacturer": manufacturer_id},
        )
        before = [
            dict(row)
            for row in connection.execute(
                text("SELECT * FROM promotions WHERE manufacturer_id = :id ORDER BY slug"),
                {"id": manufacturer_id},
            ).mappings()
        ]
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=migration_environment)
    with postgres_engine.connect() as connection:
        after = [
            dict(row)
            for row in connection.execute(
                text("SELECT * FROM promotions WHERE manufacturer_id = :id ORDER BY slug"),
                {"id": manufacturer_id},
            ).mappings()
        ]
        for row in after:
            assert row.pop("claim_start_offset_days") is None
            assert row.pop("claim_end_offset_days") is None
        assert after == before
        context = MigrationContext.configure(
            connection,
            opts={
                "include_object": lambda obj, name, kind, reflected, other: (
                    name != "test_session_isolation_probe"
                )
            },
        )
        assert compare_metadata(context, Base.metadata) == []
    inspector = inspect(postgres_engine)
    columns = {column["name"]: column for column in inspector.get_columns("promotions")}
    for name in offsets:
        assert isinstance(columns[name]["type"], Integer)
        assert columns[name]["nullable"]
        assert columns[name]["default"] is None
    constraints = {
        "ck_promotions_claim_offset_days_complete",
        "ck_promotions_claim_offset_days_nonnegative",
        "ck_promotions_claim_offset_days",
        "ck_promotions_claim_window_single_type",
    }
    assert constraints <= {check["name"] for check in inspector.get_check_constraints("promotions")}
    assert all(
        not offsets & set(index["column_names"]) for index in inspector.get_indexes("promotions")
    )
    assert "claim_window_type" not in columns
    subprocess.run(
        ["alembic", "downgrade", "0004_fixed_claim_windows"], check=True, env=migration_environment
    )
    inspector = inspect(postgres_engine)
    columns = {column["name"] for column in inspector.get_columns("promotions")}
    assert not offsets & columns
    assert fixed <= columns
    assert not constraints & {
        check["name"] for check in inspector.get_check_constraints("promotions")
    }
    assert {"ck_promotions_claim_dates_complete", "ck_promotions_claim_dates"} <= {
        check["name"] for check in inspector.get_check_constraints("promotions")
    }
    with postgres_engine.connect() as connection:
        assert [
            dict(row)
            for row in connection.execute(
                text("SELECT * FROM promotions WHERE manufacturer_id = :id ORDER BY slug"),
                {"id": manufacturer_id},
            ).mappings()
        ] == before
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=migration_environment)
    with postgres_engine.begin() as connection:
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0006_promotion_requirements"
        )
        connection.execute(
            text("DELETE FROM promotions WHERE manufacturer_id = :id"), {"id": manufacturer_id}
        )
        connection.execute(
            text("DELETE FROM manufacturers WHERE id = :id"), {"id": manufacturer_id}
        )


def test_requirement_constraint_upgrade_and_safe_downgrade(
    postgres_engine: Engine, migrated_test_database: None
) -> None:
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = postgres_engine.url.render_as_string(
        hide_password=False
    )

    def migrate(direction: str, target: str, *, check: bool = True):
        return subprocess.run(
            ["alembic", direction, target],
            check=check,
            env=migration_environment,
            capture_output=True,
            text=True,
        )

    def persisted_rows():
        with postgres_engine.connect() as connection:
            return connection.execute(
                select(Requirement.__table__)
                .where(Requirement.promotion_variant_id == variant_id)
                .order_by(Requirement.id)
            ).all()

    def constraint_values() -> set[str]:
        constraint = next(
            check
            for check in inspect(postgres_engine).get_check_constraints("requirements")
            if check["name"] == "ck_requirements_type"
        )
        return set(re.findall(r"'([^']+)'", constraint["sqltext"]))

    def revision() -> str:
        with postgres_engine.connect() as connection:
            return connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()

    legacy_types = {"receipt", "serial_number", "registration", "invoice", "barcode", "imei"}
    canonical_types = {member.value for member in RequirementType}
    migrate("downgrade", "0005_relative_claim_windows")
    assert revision() == "0005_relative_claim_windows"
    assert constraint_values() == legacy_types
    with Session(postgres_engine) as session, session.begin():
        manufacturer = Manufacturer(name="Requirements", slug="requirements")
        promotion = Promotion(
            manufacturer=manufacturer, name="Requirements", slug="requirements", status="review"
        )
        variant = PromotionVariant(promotion=promotion, code="requirements")
        variant.requirements = [
            Requirement(requirement_type=value, description=f"  Instructions for {value}.\n")
            for value in sorted(legacy_types)
        ] + [Requirement(requirement_type="receipt")]
        session.add(promotion)
        session.flush()
        manufacturer_id, promotion_id, variant_id = manufacturer.id, promotion.id, variant.id
    before = persisted_rows()
    try:
        migrate("upgrade", "head")
        assert revision() == "0006_promotion_requirements"
        assert persisted_rows() == before
        assert constraint_values() == canonical_types
        metadata_constraint = next(
            constraint
            for constraint in Requirement.__table__.constraints
            if isinstance(constraint, CheckConstraint) and constraint.name == "ck_requirements_type"
        )
        assert set(re.findall(r"'([^']+)'", str(metadata_constraint.sqltext))) == canonical_types
        # Autogenerate does not compare CHECK expressions; verify their values explicitly above.
        with postgres_engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={
                    "include_object": lambda obj, name, kind, reflected, other: (
                        name != "test_session_isolation_probe"
                    )
                },
            )
            assert compare_metadata(context, Base.metadata) == []
        with pytest.raises(IntegrityError) as error, postgres_engine.begin() as connection:
            connection.execute(
                Requirement.__table__.insert().values(
                    promotion_variant_id=variant_id, requirement_type="unsupported"
                )
            )
        assert error.value.orig.diag.constraint_name == "ck_requirements_type"
        assert persisted_rows() == before

        migrate("downgrade", "-1")
        assert revision() == "0005_relative_claim_windows"
        assert constraint_values() == legacy_types
        assert persisted_rows() == before
        with pytest.raises(IntegrityError) as error, postgres_engine.begin() as connection:
            connection.execute(
                Requirement.__table__.insert().values(
                    promotion_variant_id=variant_id, requirement_type="installation_evidence"
                )
            )
        assert error.value.orig.diag.constraint_name == "ck_requirements_type"
        migrate("upgrade", "head")
        assert persisted_rows() == before
        with postgres_engine.begin() as connection:
            connection.execute(
                Requirement.__table__.insert().values(
                    promotion_variant_id=variant_id,
                    requirement_type="installation_evidence",
                    description="Provide an installation certificate.",
                )
            )
        with_installation = persisted_rows()
        failed = migrate("downgrade", "-1", check=False)
        assert failed.returncode != 0
        assert "ck_requirements_type" in failed.stderr
        assert revision() == "0006_promotion_requirements"
        assert constraint_values() == canonical_types
        assert persisted_rows() == with_installation
        # The restored constraint remains usable after failed transactional DDL.
        with postgres_engine.begin() as connection:
            connection.execute(
                Requirement.__table__.insert().values(
                    promotion_variant_id=variant_id, requirement_type="installation_evidence"
                )
            )
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(Promotion.__table__.delete().where(Promotion.id == promotion_id))
            connection.execute(
                Manufacturer.__table__.delete().where(Manufacturer.id == manufacturer_id)
            )
        migrate("upgrade", "head")
