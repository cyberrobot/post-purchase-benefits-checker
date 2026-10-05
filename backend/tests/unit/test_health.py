import sys

from fastapi.testclient import TestClient

from app import main
from app.core.config import Settings
from app.main import create_app


def test_health_is_public_and_does_not_expose_configuration() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://secret-user:secret-password@localhost/benefits",
        SENTRY_DSN="https://public@example.ingest.sentry.io/12345",
    )
    app = create_app(settings)

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "secret" not in response.text
    assert "sentry" not in response.text.lower()


def test_unexpected_errors_return_generic_server_error_with_internal_traceback(
    monkeypatch,
) -> None:
    app = create_app(
        Settings(
            _env_file=None,
            APP_ENV="test",
            DATABASE_URL="postgresql+psycopg://user:password@localhost/benefits",
        )
    )

    @app.get("/failure")
    def fail() -> None:
        raise RuntimeError("private failure details")

    captured_log_calls = []
    original_logger = main.logger
    original_exception_logger = original_logger.exception

    def capture_exception_log(*args, **kwargs):
        captured_log_calls.append((sys.exc_info(), args, kwargs))
        return original_exception_logger(*args, **kwargs)

    class ExceptionLoggerSpy:
        def __getattr__(self, name):
            return getattr(original_logger, name)

        def exception(self, *args, **kwargs):
            return capture_exception_log(*args, **kwargs)

    monkeypatch.setattr(main, "logger", ExceptionLoggerSpy())
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/failure")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    assert "private failure details" not in response.text
    assert len(captured_log_calls) == 1
    logged_exception, args, fields = captured_log_calls[0]
    assert logged_exception[0] is RuntimeError
    assert args == ("unhandled_request_error",)
    assert fields == {
        "http_method": "GET",
        "http_path": "/failure",
        "error_type": "RuntimeError",
    }
