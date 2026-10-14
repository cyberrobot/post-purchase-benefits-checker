"""Read-only MCP boundary; wire projection and eligibility remain shared with REST."""

import json
from collections import Counter
from datetime import date
from decimal import Decimal
from threading import Event
from time import monotonic
from uuid import uuid4

import anyio
import sentry_sdk
import structlog
from mcp.server import MCPServer
from mcp.shared.exceptions import MCPError
from mcp_types import CallToolResult, TextContent, Tool, ToolAnnotations
from pydantic import TypeAdapter, ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api.eligibility import _safe_exception_event, uk_evaluation_date
from app.api.schemas.eligibility import CheckResponse, PurchaseRequest, map_result
from app.application.identity_matching import IdentityPersistenceError
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.application.purchase_check_details import PublishedPromotionDataError
from app.db.repositories.promotions import PurchaseCheckCancelled, purchase_check_snapshot

logger = structlog.get_logger(__name__)
MAX_ARGUMENT_BYTES = 8192
# Bound an in-flight PostgreSQL statement; cooperative cancellation prevents
# the worker from starting any later query after the caller disconnects.
DB_STATEMENT_TIMEOUT_MS = 5_000
DISCONNECT_POLL_INTERVAL_SECONDS = 0.05
DESCRIPTION = (
    "Check a UK purchase for published manufacturer benefits. Returns matching offers, "
    "eligibility reasons, claim windows, required evidence and official source links. "
    "Does not submit a claim or guarantee acceptance."
)
OUTPUT_SCHEMA = {"type": "object", **TypeAdapter(CheckResponse).json_schema()}


class PurchaseMCPServer(MCPServer):
    """Explicit schemas and raw dispatch avoid SDK coercion and union wrapping."""

    def __init__(self, session_factory, settings):
        super().__init__("Post-Purchase Benefits Checker")
        self.session_factory = session_factory
        self.app_settings = settings

    async def list_tools(self):
        return [
            Tool(
                name="check_purchase",
                title="Check post-purchase benefits",
                description=DESCRIPTION,
                input_schema=PurchaseRequest.model_json_schema(),
                output_schema=OUTPUT_SCHEMA,
                annotations=ToolAnnotations(
                    read_only_hint=True,
                    idempotent_hint=True,
                    destructive_hint=False,
                    open_world_hint=False,
                ),
            )
        ]

    async def call_tool(self, name, arguments, context=None):
        if name != "check_purchase":
            raise MCPError(-32602, "Unknown tool")
        request_context = getattr(context, "request_context", None)
        request = getattr(request_context, "request", None)
        result = None
        cancellation_event = Event()
        try:
            async with anyio.create_task_group() as tasks:

                async def execute():
                    nonlocal result
                    # Own the worker through rollback/closure; its sibling observes
                    # parent cancellation while this await is shielded.
                    with anyio.CancelScope(shield=True):
                        result = await anyio.to_thread.run_sync(
                            self.execute, arguments, cancellation_event
                        )
                    tasks.cancel_scope.cancel()

                async def watch_disconnect():
                    try:
                        if request is None:
                            await anyio.sleep_forever()
                        else:
                            while not await request.is_disconnected():
                                await anyio.sleep(DISCONNECT_POLL_INTERVAL_SECONDS)
                            tasks.cancel_scope.cancel()
                    finally:
                        cancellation_event.set()

                tasks.start_soon(watch_disconnect)
                tasks.start_soon(execute)
        finally:
            cancellation_event.set()
        if result is None:
            raise MCPError(-32603, "Purchase check interrupted")
        return result

    def execute(self, arguments, cancellation_event: Event | None = None):
        request_id = str(uuid4())
        started = monotonic()

        def failure(code, category, message):
            logger.warning(
                "mcp_check_purchase_failed",
                request_id=request_id,
                category=category,
                error_code=code,
            )
            return CallToolResult(
                is_error=True,
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {"code": code, "message": message, "request_id": request_id}
                        ),
                    )
                ],
            )

        try:
            encoded = json.dumps(arguments, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(encoded) > MAX_ARGUMENT_BYTES:
                return failure("request_too_large", "validation", "Arguments exceed 8192 bytes.")
            body = PurchaseRequest.model_validate(arguments)
            purchase = CheckPurchaseRequest(
                body.brand,
                body.model,
                body.retailer,
                date.fromisoformat(body.purchase_date),
                Decimal(body.purchase_price) if body.purchase_price is not None else None,
            )
        except (ValidationError, ValueError, TypeError, RecursionError):
            return failure(
                "invalid_purchase_request", "validation", "Provide valid purchase fields."
            )

        try:
            evaluation_date = uk_evaluation_date()
            snapshot_options = {"statement_timeout_ms": DB_STATEMENT_TIMEOUT_MS}
            if cancellation_event is not None:
                snapshot_options["cancellation_event"] = cancellation_event
            with purchase_check_snapshot(self.session_factory, **snapshot_options) as (
                resolver,
                repository,
            ):
                if cancellation_event is not None and cancellation_event.is_set():
                    raise PurchaseCheckCancelled
                result = check_purchase(
                    purchase,
                    evaluation_date=evaluation_date,
                    identity_resolver=resolver,
                    promotion_repository=repository,
                )
                if cancellation_event is not None and cancellation_event.is_set():
                    raise PurchaseCheckCancelled
                data = map_result(result, evaluation_date).model_dump(mode="json")
            promotions = data.get("promotions", [])
            response = CallToolResult(
                structured_content=data,
                content=[
                    TextContent(
                        type="text", text=f"{data['outcome']}; {len(promotions)} matching variants."
                    )
                ],
            )
            logger.info(
                "mcp_check_purchase_completed",
                request_id=request_id,
                duration_ms=round((monotonic() - started) * 1000),
                outcome=data["outcome"],
                candidate_count=len(promotions),
                classification_counts=dict(
                    Counter(p["eligibility"]["classification"] for p in promotions)
                ),
            )
            return response
        except PurchaseCheckCancelled:
            return failure("eligibility_unavailable", "persistence", "Purchase check interrupted.")
        except PublishedPromotionDataError:
            return failure(
                "published_data_invalid", "data_integrity", "Unable to check this purchase."
            )
        except (IdentityPersistenceError, PromotionPersistenceError, SQLAlchemyError):
            return failure("eligibility_unavailable", "persistence", "Try again later.")
        except Exception as exc:
            if self.app_settings.sentry_dsn:
                try:
                    with sentry_sdk.new_scope() as scope:
                        scope.set_tag("request_id", request_id)
                        scope.add_event_processor(_safe_exception_event)
                        sentry_sdk.capture_exception(exc)
                except Exception:
                    pass
            return failure("internal_server_error", "unexpected", "Unable to check this purchase.")
