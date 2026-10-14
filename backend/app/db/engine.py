from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import QueuePool

from app.core.config import Settings

DB_CONNECT_TIMEOUT_SECONDS = 5
DB_POOL_TIMEOUT_SECONDS = 5
DB_STATEMENT_TIMEOUT_MS = 5_000


def create_database_engine(settings: Settings) -> Engine:
    """Create the pooled PostgreSQL engine owned by an application instance."""
    url = make_url(str(settings.database_url))
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return create_engine(
        url,
        poolclass=QueuePool,
        pool_pre_ping=True,
        pool_timeout=DB_POOL_TIMEOUT_SECONDS,
        connect_args={
            # Bound a fresh connection and dead TCP peers. Psycopg 3/libpq does
            # not support a socket_timeout connection parameter.
            "connect_timeout": DB_CONNECT_TIMEOUT_SECONDS,
            "keepalives": 1,
            "keepalives_idle": 5,
            "keepalives_interval": 1,
            "keepalives_count": 3,
            # This is active from connection startup, including SQLAlchemy's
            # pre-ping and the transaction setup before per-use timeouts apply.
            "options": f"-c statement_timeout={DB_STATEMENT_TIMEOUT_MS}",
        },
    )
