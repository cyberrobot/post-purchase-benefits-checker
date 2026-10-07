"""SQLAlchemy promotion adapter. No lifecycle rules or hard-delete operation."""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import date
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.promotion_candidate_matching import PromotionCandidate
from app.application.promotions import PromotionPersistenceError, PromotionRecord
from app.db.models import (
    Promotion,
    PromotionSource,
    PromotionVariant,
    PromotionVariantProduct,
    Source,
)
from app.domain.promotion_lifecycle import HISTORICAL_PUBLISHED_STATUSES, PromotionStatus
from app.domain.promotion_provenance import PromotionSourceRecord


def _record(row: Promotion) -> PromotionRecord:
    return PromotionRecord(
        row.id,
        row.manufacturer_id,
        row.name,
        row.slug,
        PromotionStatus(row.status),
        row.purchase_start_date,
        row.purchase_end_date,
        row.created_at,
        row.updated_at,
        claim_start_date=row.claim_start_date,
        claim_end_date=row.claim_end_date,
    )


class SqlAlchemyPromotionRepository:
    """Lifecycle methods need a dedicated session; candidate reads suppress autoflush."""

    def __init__(self, session: Session):
        self.session = session

    def find_promotion_candidates(
        self,
        *,
        manufacturer_id: UUID,
        product_id: UUID,
        retailer_id: UUID,
        purchase_date: date,
    ) -> tuple[PromotionCandidate, ...]:
        """Caller-owned read transaction; only scalar candidate fields, with no autoflush."""
        query = (
            select(
                Promotion.id,
                PromotionVariant.id,
                Promotion.status,
                PromotionVariant.retailer_id,
                Promotion.purchase_start_date,
                Promotion.purchase_end_date,
            )
            .join(PromotionVariant, PromotionVariant.promotion_id == Promotion.id)
            .join(
                PromotionVariantProduct,
                PromotionVariantProduct.promotion_variant_id == PromotionVariant.id,
            )
            .where(
                Promotion.manufacturer_id == manufacturer_id,
                Promotion.status.in_([PromotionStatus.ACTIVE, *HISTORICAL_PUBLISHED_STATUSES]),
                PromotionVariantProduct.product_id == product_id,
                or_(
                    PromotionVariant.retailer_id.is_(None),
                    PromotionVariant.retailer_id == retailer_id,
                ),
                or_(
                    Promotion.purchase_start_date.is_(None),
                    Promotion.purchase_start_date <= purchase_date,
                ),
                or_(
                    Promotion.purchase_end_date.is_(None),
                    Promotion.purchase_end_date >= purchase_date,
                ),
            )
            .order_by(Promotion.created_at.desc(), Promotion.id, PromotionVariant.id)
        )
        try:
            with self.session.no_autoflush:
                return tuple(
                    PromotionCandidate(
                        row[0], row[1], PromotionStatus(row[2]), row[3], row[4], row[5]
                    )
                    for row in self.session.execute(query)
                )
        except SQLAlchemyError:
            raise PromotionPersistenceError("Promotion candidate query failed") from None

    def get_promotion(self, promotion_id: UUID) -> PromotionRecord | None:
        try:
            row = self.session.scalar(
                select(Promotion)
                .where(Promotion.id == promotion_id)
                .execution_options(populate_existing=True)
            )
            return _record(row) if row is not None else None
        except SQLAlchemyError:
            raise PromotionPersistenceError("Promotion lookup failed") from None

    def list_promotions(
        self, statuses: Iterable[PromotionStatus] | None = None
    ) -> list[PromotionRecord]:
        query = select(Promotion).order_by(Promotion.created_at.desc(), Promotion.id)
        if statuses is not None:
            query = query.where(Promotion.status.in_([PromotionStatus(s).value for s in statuses]))
        try:
            return [
                _record(row)
                for row in self.session.scalars(query.execution_options(populate_existing=True))
            ]
        except SQLAlchemyError:
            raise PromotionPersistenceError("Promotion query failed") from None

    def list_active_promotions(self) -> list[PromotionRecord]:
        return self.list_promotions([PromotionStatus.ACTIVE])

    def list_historical_promotions(
        self, statuses: Iterable[PromotionStatus] | None = None
    ) -> list[PromotionRecord]:
        selected = (
            HISTORICAL_PUBLISHED_STATUSES
            if statuses is None
            else frozenset(PromotionStatus(s) for s in statuses)
        )
        if not selected <= HISTORICAL_PUBLISHED_STATUSES:
            raise ValueError("Historical published queries require expired states")
        return self.list_promotions(selected)

    def list_promotion_sources(self, promotion_id: UUID) -> list[PromotionSourceRecord]:
        try:
            rows = self.session.execute(
                select(
                    Source.id,
                    PromotionSource.role,
                    Source.url,
                    Source.source_type,
                    Source.retrieved_at,
                    Source.verified_at,
                )
                .join(PromotionSource, PromotionSource.source_id == Source.id)
                .where(PromotionSource.promotion_id == promotion_id)
            )
            return [PromotionSourceRecord(*row) for row in rows]
        except SQLAlchemyError:
            raise PromotionPersistenceError("Promotion provenance query failed") from None

    def update_status(
        self, promotion_id: UUID, expected: PromotionStatus, target: PromotionStatus
    ) -> bool:
        expected, target = PromotionStatus(expected), PromotionStatus(target)
        try:
            result = self.session.execute(
                update(Promotion)
                .where(Promotion.id == promotion_id, Promotion.status == expected)
                .values(status=target.value)
                .execution_options(synchronize_session=False)
            )
            return result.rowcount == 1
        except SQLAlchemyError:
            raise PromotionPersistenceError("Promotion update failed") from None


@contextmanager
def promotion_transaction(
    session_factory: Callable[[], Session],
) -> Iterator[SqlAlchemyPromotionRepository]:
    """Commit on success; rollback and close on every failure, including commit failure."""
    try:
        with session_factory() as session, session.begin():
            yield SqlAlchemyPromotionRepository(session)
    except SQLAlchemyError:
        raise PromotionPersistenceError("Promotion transaction failed") from None
