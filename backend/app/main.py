from collections.abc import Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.health import router as health_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.core.sentry import initialise_sentry
from app.db.engine import create_database_engine

logger = structlog.get_logger(__name__)


def create_app(
    settings: Settings | None = None,
    *,
    engine_factory: Callable[[Settings], Engine] = create_database_engine,
) -> FastAPI:
    """Build an isolated FastAPI app and its database resources."""
    app_settings = settings or get_settings()
    engine = engine_factory(app_settings)
    session_factory = sessionmaker(bind=engine, class_=Session, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("application_started", environment=app_settings.app_env)
        yield
        engine.dispose()
        logger.info("application_stopped")

    app = FastAPI(title="Post-Purchase Benefits Checker API", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.include_router(health_router)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_request_error",
            http_method=request.method,
            http_path=request.url.path,
            error_type=type(exc).__name__,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    return app


settings = get_settings()
configure_logging(settings.log_level)
initialise_sentry(settings)
app = create_app(settings)
