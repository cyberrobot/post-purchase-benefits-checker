import os
import subprocess
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from testcontainers.community.postgres import PostgresContainer

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://benefits:benefits@localhost:5432/benefits",
)
os.environ.setdefault("APP_ENV", "test")


@pytest.fixture(scope="session")
def postgres_engine() -> Iterator[Engine]:
    """Start an isolated real PostgreSQL server and apply the fresh-schema migration."""
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        database_url = postgres.get_connection_url()
        engine = create_engine(database_url, pool_pre_ping=True)
        migration_environment = os.environ.copy()
        migration_environment["DATABASE_URL"] = database_url
        try:
            subprocess.run(
                ["alembic", "upgrade", "head"],
                check=True,
                env=migration_environment,
            )
            yield engine
        finally:
            engine.dispose()
