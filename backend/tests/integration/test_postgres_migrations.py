import os
import subprocess

import pytest
from sqlalchemy import inspect, text
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
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = postgres_engine.url.render_as_string(
        hide_password=False
    )
    subprocess.run(["alembic", "downgrade", "-1"], check=True, env=migration_environment)
    with postgres_engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
            == "0001_initial_baseline"
        )
    assert not set(Base.metadata.tables) & set(inspect(postgres_engine).get_table_names())
    assert "test_session_isolation_probe" in inspect(postgres_engine).get_table_names()
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=migration_environment)
    with postgres_engine.connect() as connection:
        final_revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert revision == "0002_core_promotion_schema"
    assert final_revision == "0002_core_promotion_schema"
    assert set(Base.metadata.tables) <= set(inspect(postgres_engine).get_table_names())
