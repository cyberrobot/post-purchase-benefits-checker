from types import SimpleNamespace

import pytest
from starlette.requests import Request

from app.db.session import get_session


class FakeSession:
    def __init__(self) -> None:
        self.rollback_called = False
        self.close_called = False

    def rollback(self) -> None:
        self.rollback_called = True

    def close(self) -> None:
        self.close_called = True


def request_for(session: FakeSession) -> Request:
    app = SimpleNamespace(state=SimpleNamespace(session_factory=lambda: session))
    return Request({"type": "http", "app": app})


def test_session_is_closed_after_success() -> None:
    session = FakeSession()
    dependency = get_session(request_for(session))

    assert next(dependency) is session
    with pytest.raises(StopIteration):
        next(dependency)

    assert session.close_called
    assert not session.rollback_called


def test_failed_request_rolls_back_and_closes_session() -> None:
    session = FakeSession()
    dependency = get_session(request_for(session))
    next(dependency)

    with pytest.raises(RuntimeError, match="request failed"):
        dependency.throw(RuntimeError("request failed"))

    assert session.rollback_called
    assert session.close_called
