from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import QueuePool

from app.core.config import Settings


def create_database_engine(settings: Settings) -> Engine:
    """Create the pooled PostgreSQL engine owned by an application instance."""
    url = make_url(str(settings.database_url))
    if url.drivername in {"postgres", "postgresql"}:
        url = url.set(drivername="postgresql+psycopg")
    return create_engine(
        url,
        poolclass=QueuePool,
        pool_pre_ping=True,
    )
