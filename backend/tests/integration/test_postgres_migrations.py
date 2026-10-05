import os
import subprocess

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

pytestmark = pytest.mark.integration


def test_fresh_postgres_connectivity_and_migration_head(postgres_engine: Engine) -> None:
    with postgres_engine.connect() as connection:
        assert connection.execute(text("SELECT 1")).scalar_one() == 1
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = postgres_engine.url.render_as_string(
        hide_password=False
    )
    subprocess.run(["alembic", "downgrade", "-1"], check=True, env=migration_environment)
    with postgres_engine.connect() as connection:
        assert (
            connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            is None
        )
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=migration_environment)
    with postgres_engine.connect() as connection:
        final_revision = connection.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()

    assert revision == "0001_initial_baseline"
    assert final_revision == "0001_initial_baseline"
