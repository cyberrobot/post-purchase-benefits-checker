import sentry_sdk

from app.core.config import Settings


def initialise_sentry(settings: Settings) -> None:
    """Enable error reporting only when an operator supplies a DSN."""
    if not settings.sentry_dsn:
        return
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        send_default_pii=False,
        include_local_variables=False,
    )
