"""Public, read-only published promotion route."""

from time import monotonic
from uuid import uuid4

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api.eligibility import _report_unexpected_exception
from app.api.schemas.eligibility import Problem
from app.api.schemas.promotions import PromotionDetails, map_promotion
from app.application.promotion_details import LookupNotFound, get_public_promotion
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check_details import PublishedPromotionDataError
from app.db.repositories.promotions import purchase_check_snapshot
from app.domain.promotion_identity import is_slug

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/v1/promotions", tags=["Promotions v1"])
ERRORS = {
    404: ("promotion_not_found", "Promotion not found", "This promotion is unavailable."),
    500: ("published_data_invalid", "Promotion details unavailable", "Try again later."),
    503: ("promotions_unavailable", "Promotion details unavailable", "Try again later."),
}


@router.get(
    "/{manufacturer_slug}/{promotion_slug}",
    response_model=PromotionDetails,
    responses={
        status: {
            "description": title,
            "content": {"application/problem+json": {"schema": Problem.model_json_schema()}},
        }
        for status, (_, title, _) in ERRORS.items()
    },
)
def promotion_details(manufacturer_slug: str, promotion_slug: str, request: Request):
    request_id = uuid4()
    headers = {"X-Request-ID": str(request_id), "Cache-Control": "no-store"}
    start = monotonic()
    error = None
    try:
        if not is_slug(manufacturer_slug) or not is_slug(promotion_slug):
            raise LookupNotFound
        raw_path = request.scope.get("raw_path", b"")
        if b"%" in raw_path:
            raise LookupNotFound
        with purchase_check_snapshot(
            request.app.state.session_factory, statement_timeout_ms=5000
        ) as (
            _,
            repository,
        ):
            details = map_promotion(
                *get_public_promotion(repository, manufacturer_slug, promotion_slug)
            )
        response = JSONResponse(details.model_dump(mode="json"), headers=headers)
    except LookupNotFound:
        status, error = 404, "not_found"
    except (PublishedPromotionDataError, ValidationError):
        status, error = 500, "data_integrity"
    except (PromotionPersistenceError, SQLAlchemyError):
        status, error = 503, "persistence"
    except Exception as exc:
        status, error = 500, "unexpected"
        _report_unexpected_exception(request, exc, request_id)
    if error is not None:
        code, title, detail = ERRORS[status]
        if error == "unexpected":
            code = "internal_server_error"
        response = JSONResponse(
            Problem(
                title=title, status=status, detail=detail, code=code, request_id=request_id
            ).model_dump(mode="json"),
            status_code=status,
            media_type="application/problem+json",
            headers=headers,
        )
    logger.info(
        "promotion_details_http_read",
        status=response.status_code,
        request_id=str(request_id),
        duration_ms=round((monotonic() - start) * 1000),
        category=error or "success",
    )
    return response
