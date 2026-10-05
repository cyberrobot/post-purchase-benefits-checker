from unittest.mock import Mock

import sentry_sdk

from app.core.config import Settings
from app.core.sentry import initialise_sentry
from app.main import create_app


def make_settings(sentry_dsn: str | None) -> Settings:
    return Settings(
        _env_file=None,
        APP_ENV="test",
        DATABASE_URL="postgresql+psycopg://user:password@localhost/benefits",
        SENTRY_DSN=sentry_dsn,
    )


def test_sentry_is_not_initialized_without_a_dsn(monkeypatch) -> None:
    sentry_init = Mock()
    monkeypatch.setattr(sentry_sdk, "init", sentry_init)

    initialise_sentry(make_settings(None))

    sentry_init.assert_not_called()


def test_sentry_initialization_keeps_privacy_settings(monkeypatch) -> None:
    sentry_init = Mock()
    monkeypatch.setattr(sentry_sdk, "init", sentry_init)
    settings = make_settings("https://public@example.ingest.sentry.io/12345")

    initialise_sentry(settings)

    sentry_init.assert_called_once_with(
        dsn=settings.sentry_dsn,
        environment="test",
        send_default_pii=False,
        include_local_variables=False,
    )


def test_app_factory_does_not_leak_sentry_state_between_apps(monkeypatch) -> None:
    sentry_init = Mock()
    monkeypatch.setattr(sentry_sdk, "init", sentry_init)

    configured_app = create_app(make_settings("https://public@example.ingest.sentry.io/12345"))
    unconfigured_app = create_app(make_settings(None))

    assert configured_app is not unconfigured_app
    sentry_init.assert_not_called()
