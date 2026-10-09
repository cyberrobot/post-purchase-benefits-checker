"""Promotion contracts and lifecycle orchestration."""

from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

import structlog

from app.domain.promotion_lifecycle import PromotionStatus, validate_transition
from app.domain.promotion_provenance import PromotionSourceRecord
from app.domain.promotion_validation import (
    PromotionValidationSnapshot,
    ValidationReport,
    validate_promotion_for_publication,
)

logger = structlog.get_logger(__name__)


class PromotionPublicationError(ValueError):
    def __init__(self, report: ValidationReport):
        self.report = report
        super().__init__("Promotion publication validation rejected")


class PromotionNotFound(LookupError):
    pass


class PromotionConflict(RuntimeError):
    pass


class PromotionPersistenceError(RuntimeError):
    """Safe infrastructure failure; never interpreted as a domain rejection."""


@dataclass(frozen=True)
class PromotionRecord:
    id: UUID
    manufacturer_id: UUID
    name: str
    slug: str
    status: PromotionStatus
    purchase_start_date: date | None
    purchase_end_date: date | None
    created_at: datetime
    updated_at: datetime
    claim_start_date: date | None = None
    claim_end_date: date | None = None
    claim_start_offset_days: int | None = None
    claim_end_offset_days: int | None = None


@dataclass(frozen=True)
class StatusChange:
    promotion_id: UUID
    previous_status: PromotionStatus
    target_status: PromotionStatus
    changed: bool


class PromotionRepository(Protocol):
    def get_publication_snapshot_for_update(
        self, promotion_id: UUID
    ) -> PromotionValidationSnapshot | None: ...
    def get_promotion(self, promotion_id: UUID) -> PromotionRecord | None: ...
    def list_promotions(
        self, statuses: Iterable[PromotionStatus] | None = None
    ) -> list[PromotionRecord]: ...
    def list_active_promotions(self) -> list[PromotionRecord]: ...
    def list_historical_promotions(
        self, statuses: Iterable[PromotionStatus] | None = None
    ) -> list[PromotionRecord]: ...
    def list_promotion_sources(self, promotion_id: UUID) -> list[PromotionSourceRecord]: ...
    def update_status(
        self, promotion_id: UUID, expected: PromotionStatus, target: PromotionStatus
    ) -> bool: ...


TransactionFactory = Callable[[], AbstractContextManager[PromotionRepository]]


def change_promotion_status(
    transaction: TransactionFactory, promotion_id: UUID, target_status: PromotionStatus
) -> StatusChange:
    """Own one atomic transaction; reconcile stale writes without overwriting them."""
    target = PromotionStatus(target_status)
    publication_attempt = False
    validated = False
    try:
        with transaction() as repository:
            promotion = repository.get_promotion(promotion_id)
            if promotion is None:
                raise PromotionNotFound(promotion_id)
            previous = promotion.status
            changed = validate_transition(previous, target)
            if changed and target == PromotionStatus.ACTIVE:
                publication_attempt = True
                snapshot = repository.get_publication_snapshot_for_update(promotion_id)
                if snapshot is None:
                    raise PromotionNotFound(promotion_id)
                current = repository.get_promotion(promotion_id)
                if current is None:
                    raise PromotionNotFound(promotion_id)
                if current.status != previous:
                    if current.status != target:
                        raise PromotionConflict(promotion_id)
                    changed = False
                else:
                    report = validate_promotion_for_publication(snapshot)
                    if not report.can_publish:
                        raise PromotionPublicationError(report)
                    validated = True
            if changed and not repository.update_status(promotion_id, previous, target):
                current = repository.get_promotion(promotion_id)
                if current is None or current.status != target:
                    raise PromotionConflict(promotion_id)
                changed = False
            result = StatusChange(promotion_id, previous, target, changed)
    except PromotionPublicationError as error:
        logger.info(
            "publication_validation_rejected",
            promotion_id=str(promotion_id),
            issue_count=len(error.report.issues),
            issue_codes=[i.code for i in error.report.issues],
        )
        raise
    except PromotionPersistenceError:
        if publication_attempt or target == PromotionStatus.ACTIVE:
            logger.error(
                "publication_validation_failed",
                promotion_id=str(promotion_id),
                issue_count=0,
                issue_codes=[],
            )
        raise
    if validated:
        logger.info(
            "publication_validation_succeeded",
            promotion_id=str(promotion_id),
            issue_count=0,
            issue_codes=[],
        )
    return result
