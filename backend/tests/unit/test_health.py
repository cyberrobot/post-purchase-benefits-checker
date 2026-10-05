from fastapi.testclient import TestClient

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


def test_unexpected_errors_return_generic_server_error() -> None:
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

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/failure")

    assert response.status_code == 500
    assert response.json() == {"detail": "Internal Server Error"}
    assert "private failure details" not in response.text
