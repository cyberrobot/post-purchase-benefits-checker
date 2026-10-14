from collections.abc import Callable
from contextlib import AsyncExitStack, asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.api.eligibility import router as eligibility_router
from app.api.health import router as health_router
from app.api.schemas.eligibility import ResolvedResponse
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

    mcp = None
    mcp_app = None
    if app_settings.mcp_http_enabled:
        from app.mcp.local_access import LoopbackOnly
        from app.mcp.server import PurchaseMCPServer

        mcp = PurchaseMCPServer(session_factory, app_settings)
        mcp_app = mcp.streamable_http_app(
            json_response=True, stateless_http=True, max_request_body_size=16384
        )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        logger.info("application_started", environment=app_settings.app_env)
        try:
            async with AsyncExitStack() as stack:
                if mcp is not None:
                    await stack.enter_async_context(mcp.session_manager.run())
                yield
        finally:
            engine.dispose()
            logger.info("application_stopped")

    app = FastAPI(title="Post-Purchase Benefits Checker API", lifespan=lifespan)
    app.state.settings = app_settings
    app.state.engine = engine
    app.state.session_factory = session_factory
    app.include_router(health_router)
    app.include_router(eligibility_router)

    original_openapi = app.openapi

    def openapi_with_complete_examples():
        schema = original_openapi()
        # FastAPI drops explicit nulls in examples. Restore the complete wire example
        # after generation so required nullable fields remain documented accurately.
        schema["components"]["schemas"]["ResolvedResponse"]["example"] = (
            ResolvedResponse.model_json_schema()["example"]
        )
        return schema

    app.openapi = openapi_with_complete_examples

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled_request_error",
            http_method=request.method,
            http_path=request.url.path,
            error_type=type(exc).__name__,
        )
        return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

    if mcp_app is not None:
        # Last mount preserves all REST, docs and OpenAPI routes; SDK owns /mcp.
        app.mount("/", LoopbackOnly(mcp_app))
        app.state.mcp_server = mcp

    return app


settings = get_settings()
configure_logging(settings.log_level)
initialise_sentry(settings)
app = create_app(settings)
