import os
import subprocess
from collections.abc import Callable, Iterator
from contextlib import AbstractContextManager, contextmanager

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session
from testcontainers.community.postgres import PostgresContainer

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg://benefits:benefits@localhost:5432/benefits",
)
os.environ.setdefault("APP_ENV", "test")
# Prevent an operator's local Sentry DSN from enabling external reporting during tests.
os.environ["SENTRY_DSN"] = ""


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Start one real PostgreSQL container for the entire test session."""
    with PostgresContainer("postgres:16-alpine", driver="psycopg") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def database_url(postgres_container: PostgresContainer) -> str:
    return postgres_container.get_connection_url()


@pytest.fixture(scope="session")
def postgres_engine(database_url: str) -> Iterator[Engine]:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture(scope="session")
def migrated_test_database(postgres_engine: Engine, database_url: str) -> None:
    """Apply migrations once and create a scratch table for transaction-isolation tests."""
    migration_environment = os.environ.copy()
    migration_environment["DATABASE_URL"] = database_url
    subprocess.run(["alembic", "upgrade", "head"], check=True, env=migration_environment)
    with postgres_engine.begin() as connection:
        connection.execute(
            text("CREATE TABLE test_session_isolation_probe (marker TEXT PRIMARY KEY)")
        )


@pytest.fixture
def db_session_factory(
    postgres_engine: Engine,
    migrated_test_database: None,
) -> Callable[[], AbstractContextManager[Session]]:
    """Return isolated transactional Sessions, each rolled back when its context exits."""

    @contextmanager
    def isolated_session() -> Iterator[Session]:
        connection = postgres_engine.connect()
        transaction = connection.begin()
        session = Session(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            try:
                session.close()
            finally:
                try:
                    if transaction.is_active:
                        transaction.rollback()
                finally:
                    connection.close()

    return isolated_session


@pytest.fixture
def db_session(
    db_session_factory: Callable[[], AbstractContextManager[Session]],
) -> Iterator[Session]:
    """Provide a per-test SQLAlchemy Session with automatic transaction rollback."""
    with db_session_factory() as session:
        yield session
