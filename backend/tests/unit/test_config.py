import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_load_validated_environment_values() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost:5432/benefits",
        LOG_LEVEL="debug",
    )

    assert settings.app_env == "test"
    assert settings.log_level == "DEBUG"
    assert settings.sentry_dsn is None


def test_database_url_is_required(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None)


def test_database_url_must_be_postgresql() -> None:
    with pytest.raises(ValidationError, match="database_url"):
        Settings(_env_file=None, DATABASE_URL="sqlite:///not-postgres.db")
