"""Public read-only adapter over the canonical purchase-check operation."""

import json
from datetime import date, datetime
from decimal import Decimal
from time import monotonic
from typing import Annotated
from uuid import uuid4
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas.eligibility import CheckResponse, Problem, PurchaseRequest, map_result
from app.application.identity_matching import IdentityPersistenceError
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.application.purchase_check_details import PublishedPromotionDataError
from app.db.repositories.promotions import purchase_check_snapshot

logger = structlog.get_logger(__name__)
MAX_BODY_BYTES = 8192
ERRORS = {
    413: ("request_too_large", "Request too large", "Request body must not exceed 8192 bytes."),
    415: ("unsupported_media_type", "Unsupported media type", "Use application/json."),
    422: (
        "invalid_purchase_request",
        "Invalid purchase request",
        "Provide valid purchase fields and try again.",
    ),
    503: ("eligibility_unavailable", "Eligibility unavailable", "Try again later."),
}


def uk_evaluation_date():
    return datetime.now(ZoneInfo("Europe/London")).date()


def problem(status, request_id, *, published=False):
    code, title, detail = ERRORS.get(
        status,
        (
            "published_data_invalid" if published else "internal_server_error",
            "Eligibility data invalid" if published else "Internal server error",
            "Unable to check this purchase.",
        ),
    )
    if status < 500:
        logger.info(
            "eligibility_http_check_failed",
            status=status,
            error_code=code,
            request_id=str(request_id),
            category="validation",
        )
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content=Problem(
            title=title, status=status, detail=detail, code=code, request_id=request_id
        ).model_dump(mode="json"),
        headers={"X-Request-ID": str(request_id)},
    )


class EligibilityRoute(APIRoute):
    """Scope body bounds and safe errors to this endpoint, including validation."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def bounded(request):
            request_id = uuid4()
            request.state.eligibility_request_id = request_id
            started = monotonic()
            try:
                chunks, size = [], 0
                async for chunk in request.stream():
                    size += len(chunk)
                    if size > MAX_BODY_BYTES:
                        return problem(413, request_id)
                    chunks.append(chunk)
                request._body = b"".join(chunks)
                if (
                    request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
                    != "application/json"
                ):
                    return problem(415, request_id)
                try:
                    json.loads(request._body.decode("utf-8"))
                except (UnicodeDecodeError, ValueError, RecursionError):
                    return problem(422, request_id)
                response = await original(request)
                response.headers["X-Request-ID"] = str(request_id)
                logger.info(
                    "eligibility_http_check_completed",
                    status=response.status_code,
                    outcome=getattr(request.state, "eligibility_outcome", "invalid_request"),
                    request_id=str(request_id),
                    duration_ms=round((monotonic() - started) * 1000),
                    candidate_count=getattr(request.state, "eligibility_candidate_count", 0),
                    classification_counts=getattr(request.state, "eligibility_classifications", {}),
                )
                return response
            except RequestValidationError:
                return problem(422, request_id)
            except PublishedPromotionDataError as exc:
                logger.error(
                    "eligibility_http_check_failed",
                    category="data_integrity",
                    error_code=exc.code.value,
                    request_id=str(request_id),
                    status=500,
                )
                return problem(500, request_id, published=True)
            except (IdentityPersistenceError, PromotionPersistenceError, SQLAlchemyError):
                logger.error(
                    "eligibility_http_check_failed",
                    category="persistence",
                    request_id=str(request_id),
                    status=503,
                )
                return problem(503, request_id)
            except Exception as exc:
                # Exception messages can contain raw purchase/SQL data; retain only type.
                logger.error(
                    "eligibility_http_check_failed",
                    category="unexpected",
                    error_type=type(exc).__name__,
                    request_id=str(request_id),
                    status=500,
                )
                return problem(500, request_id)

        return bounded


router = APIRouter(
    prefix="/api/v1/eligibility", tags=["Eligibility v1"], route_class=EligibilityRoute
)


@router.post(
    "/check",
    response_model=CheckResponse,
    responses={
        200: {
            "content": {
                "application/json": {
                    "examples": {
                        "resolved_no_match": {
                            "value": {
                                "outcome": "resolved",
                                "evaluation_date": "2026-10-08",
                                "resolved_identity": {
                                    "manufacturer_id": "00000000-0000-0000-0000-000000000001",
                                    "retailer_id": "00000000-0000-0000-0000-000000000002",
                                    "product_id": "00000000-0000-0000-0000-000000000003",
                                },
                                "promotions": [],
                                "no_match_reason": "no_matching_published_promotions",
                                "explanation": [
                                    "No matching published promotion was found for this purchase."
                                ],
                            }
                        },
                        "unresolved": {
                            "value": {
                                "outcome": "unresolved_identity",
                                "evaluation_date": "2026-10-08",
                                "unresolved_identity": {
                                    "field": "brand",
                                    "status": "not_found",
                                    "candidate_ids": [],
                                },
                                "explanation": [
                                    "The brand could not be found. Check the brand name."
                                ],
                            }
                        },
                    }
                }
            }
        },
        **{
            code: {
                "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
                "description": "Gateway rate limit" if code == 429 else "Purchase check failure",
            }
            for code in (413, 415, 422, 429, 500, 503)
        },
    },
)
def eligibility_check(
    body: PurchaseRequest,
    request: Request,
    evaluation_date: Annotated[date, Depends(uk_evaluation_date)],
):
    try:
        purchase = CheckPurchaseRequest(
            body.brand,
            body.model,
            body.retailer,
            date.fromisoformat(body.purchase_date),
            Decimal(body.purchase_price) if body.purchase_price is not None else None,
        )
    except (ValueError, TypeError):
        return problem(422, request.state.eligibility_request_id)
    with purchase_check_snapshot(request.app.state.session_factory) as (resolver, repository):
        result = check_purchase(
            purchase,
            evaluation_date=evaluation_date,
            identity_resolver=resolver,
            promotion_repository=repository,
        )
        response = map_result(result, evaluation_date)
    promotions = getattr(response, "promotions", [])
    counts = {}
    for promotion in promotions:
        classification = promotion.eligibility.classification.value
        counts[classification] = counts.get(classification, 0) + 1
    request.state.eligibility_candidate_count = len(promotions)
    request.state.eligibility_classifications = counts
    request.state.eligibility_outcome = response.outcome
    return response
