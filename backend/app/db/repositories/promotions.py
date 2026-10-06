"""SQLAlchemy promotion adapter. No lifecycle rules or hard-delete operation."""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.promotions import PromotionPersistenceError, PromotionRecord
from app.db.models import Promotion
from app.domain.promotion_lifecycle import HISTORICAL_PUBLISHED_STATUSES, PromotionStatus


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
    )


class SqlAlchemyPromotionRepository:
    """Use a dedicated, transaction-owned session; do not pass pending ORM changes."""

    def __init__(self, session: Session):
        self.session = session

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
