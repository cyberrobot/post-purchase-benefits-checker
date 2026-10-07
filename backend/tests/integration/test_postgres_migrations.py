import os
import subprocess
from uuid import uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Date, inspect, text
from sqlalchemy.engine import Engine

from app.db import models  # noqa: F401
from app.db.base import Base

pytestmark = pytest.mark.integration


def test_fresh_postgres_connectivity_and_migration_head(
    postgres_engine: Engine,
    migrated_test_database: None,
) -> None:
    with postgres_engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    assert set(Base.metadata.tables) <= set(inspect(postgres_engine).get_table_names())
    assert revision == "0004_fixed_claim_windows"
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = postgres_engine.url.render_as_string(
        hide_password=False
    )
    subprocess.run(["alembic", "downgrade", "-1"], check=True, env=migration_environment)
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

    assert revision == "0004_fixed_claim_windows"
    assert final_revision == "0004_fixed_claim_windows"
    assert set(Base.metadata.tables) <= set(inspect(postgres_engine).get_table_names())

    # Retain the original core-schema downgrade coverage as well as the new -1 round trip.
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
            == "0004_fixed_claim_windows"
        )
    assert set(Base.metadata.tables) <= set(inspect(postgres_engine).get_table_names())
