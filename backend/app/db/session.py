from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session, sessionmaker

SessionFactory = sessionmaker[Session]


def get_session(request: Request) -> Iterator[Session]:
    """Yield a request-owned session, rolling back on failure and always closing it."""
    factory: SessionFactory = request.app.state.session_factory
    session = factory()
    try:
        yield session
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
