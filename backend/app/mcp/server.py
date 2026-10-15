"""Read-only MCP boundary; wire projection and eligibility remain shared with REST."""

import json
from collections import Counter
from datetime import date
from decimal import Decimal
from threading import Event
from time import monotonic
from uuid import UUID, uuid4

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
from app.application.promotion_details import (
    InvalidLookupRequest,
    LookupNotFound,
    get_published_details,
)
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.application.purchase_check_details import PublishedPromotionDataError
from app.db.repositories.promotions import PurchaseCheckCancelled, purchase_check_snapshot
from app.domain.promotion_provenance import SourceRole
from app.domain.rewards import FixedAmountReward, PercentageReward, ProductSpecificReward
from app.mcp.schemas import LOOKUP_SCHEMAS

logger = structlog.get_logger(__name__)
MAX_ARGUMENT_BYTES = 8192
# Descriptions are unbounded database text; fail safely rather than truncate evidence.
MAX_LOOKUP_RESPONSE_BYTES = 65536
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
        ] + [
            Tool(
                name=name,
                title=title,
                description=description,
                input_schema=input_model.model_json_schema(),
                output_schema=output_model.model_json_schema(),
                annotations=ToolAnnotations(
                    read_only_hint=True,
                    idempotent_hint=True,
                    destructive_hint=False,
                    open_world_hint=False,
                ),
            )
            for name, (input_model, output_model, title, description) in LOOKUP_SCHEMAS.items()
        ]

    async def call_tool(self, name, arguments, context=None):
        if name != "check_purchase" and name not in LOOKUP_SCHEMAS:
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
                            self.execute if name == "check_purchase" else self.execute_lookup,
                            arguments if name == "check_purchase" else (name, arguments),
                            cancellation_event,
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

    def execute_lookup(self, invocation, cancellation_event: Event | None = None):
        name, arguments = invocation
        request_id = str(uuid4())
        started = monotonic()

        def failure(code, category, message):
            logger.warning(
                "mcp_lookup_failed",
                tool_name=name,
                request_id=request_id,
                category=category,
                error_code=code,
                duration_ms=round((monotonic() - started) * 1000),
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

        input_model, output_model, _, _ = LOOKUP_SCHEMAS[name]
        try:
            encoded = json.dumps(arguments, ensure_ascii=False, allow_nan=False).encode("utf-8")
            if len(encoded) > MAX_ARGUMENT_BYTES:
                return failure("request_too_large", "validation", "Arguments exceed 8192 bytes.")
            body = input_model.model_validate(arguments)
        except (ValidationError, ValueError, TypeError, RecursionError):
            return failure("invalid_lookup_request", "validation", "Provide valid lookup fields.")

        try:
            options = {"statement_timeout_ms": DB_STATEMENT_TIMEOUT_MS}
            if cancellation_event is not None:
                options["cancellation_event"] = cancellation_event
            with purchase_check_snapshot(self.session_factory, **options) as (_, repository):
                if cancellation_event is not None and cancellation_event.is_set():
                    raise PurchaseCheckCancelled
                lookup = get_published_details(repository, UUID(body.promotion_variant_id))
                details = lookup.details
                data = dict(
                    promotion_id=str(details.promotion_id),
                    promotion_variant_id=str(details.promotion_variant_id),
                    promotion_status=details.promotion_status.value,
                )
                if name == "get_benefit":
                    product_id = UUID(body.product_id) if body.product_id else None
                    benefit = lookup.benefit(UUID(body.benefit_id), product_id)
                    reward = benefit.reward
                    mapped = None
                    if reward is not None:
                        mapped = dict(
                            reward_type=reward.reward_type.value,
                            fixed_amount_gbp=None,
                            percentage=None,
                            product_id=None,
                            product_amount_gbp=None,
                            product_lookup_status="not_applicable",
                        )
                        if isinstance(reward, FixedAmountReward):
                            mapped["fixed_amount_gbp"] = format(reward.amount, "f")
                        elif isinstance(reward, PercentageReward):
                            mapped["percentage"] = format(reward.percentage, "f")
                        elif isinstance(reward, ProductSpecificReward):
                            mapped["product_lookup_status"] = "product_id_required"
                            if product_id is not None:
                                value = next(v for v in reward.values if v.product_id == product_id)
                                mapped.update(
                                    product_id=str(product_id),
                                    product_amount_gbp=format(value.amount, "f"),
                                    product_lookup_status="configured",
                                )
                    data.update(
                        benefit_id=str(benefit.benefit_id),
                        benefit_type=benefit.benefit.benefit_type,
                        name=benefit.benefit.name,
                        description=benefit.benefit.description,
                        reward=mapped,
                    )
                    text = (
                        f"Stored {benefit.benefit.benefit_type.value} benefit definition; "
                        "no personal payout calculated."
                    )
                elif name == "get_claim_requirements":
                    requirements = [
                        dict(
                            requirement_id=str(r.requirement_id),
                            requirement_type=r.requirement.requirement_type,
                            description=r.requirement.description,
                        )
                        for r in sorted(details.requirements, key=lambda r: r.requirement_id)
                    ]
                    data.update(
                        claim_url=lookup.provenance.claim_url,
                        requirements_recorded=bool(requirements),
                        requirements=requirements,
                    )
                    text = f"{len(requirements)} requirements recorded in this dataset."
                else:
                    source = lookup.source(UUID(body.source_id))
                    data.update(
                        source_id=str(source.source_id),
                        role=source.role,
                        url=source.url,
                        source_type=source.source_type,
                        retrieved_at=source.retrieved_at,
                        verified_at=source.verified_at,
                        is_official_primary_source=source.role == SourceRole.PRIMARY,
                        last_verified_at=lookup.provenance.verified_at,
                    )
                    text = f"Linked {source.role.value} source; recorded verification only."
                try:
                    validated = output_model.model_validate(data)
                except ValidationError as error:
                    raise PublishedPromotionDataError from error
                data = validated.model_dump(mode="json")
                if cancellation_event is not None and cancellation_event.is_set():
                    raise PurchaseCheckCancelled
            if (
                len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"))
                > MAX_LOOKUP_RESPONSE_BYTES
            ):
                return failure(
                    "published_data_invalid",
                    "data_integrity",
                    "Published detail exceeds response limit.",
                )
            response = CallToolResult(
                structured_content=data, content=[TextContent(type="text", text=text)]
            )
            logger.info(
                "mcp_lookup_completed",
                tool_name=name,
                request_id=request_id,
                duration_ms=round((monotonic() - started) * 1000),
                outcome="success",
            )
            return response
        except InvalidLookupRequest:
            return failure("invalid_lookup_request", "validation", "Provide valid lookup fields.")
        except LookupNotFound:
            return failure("not_found", "absence", "Published detail not found.")
        except PublishedPromotionDataError:
            return failure(
                "published_data_invalid", "data_integrity", "Unable to retrieve published detail."
            )
        except (PurchaseCheckCancelled, PromotionPersistenceError, SQLAlchemyError):
            return failure("lookup_unavailable", "persistence", "Try again later.")
        except Exception as exc:
            if self.app_settings.sentry_dsn:
                try:
                    with sentry_sdk.new_scope() as scope:
                        scope.set_tag("request_id", request_id)
                        scope.add_event_processor(_safe_exception_event)
                        sentry_sdk.capture_exception(exc)
                except Exception:
                    pass
            return failure(
                "internal_server_error", "unexpected", "Unable to retrieve published detail."
            )
