"""SQLAlchemy promotion adapter. No lifecycle rules or hard-delete operation."""

from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import date
from uuid import UUID

from sqlalchemy import or_, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from app.application.promotion_candidate_matching import PromotionCandidate
from app.application.promotions import PromotionPersistenceError, PromotionRecord
from app.db.models import (
    Benefit,
    BenefitReward,
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
        claim_start_offset_days=row.claim_start_offset_days,
        claim_end_offset_days=row.claim_end_offset_days,
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

    def load_check_purchase_candidates(self, candidate_variant_ids):
        """Batch associations inside caller snapshot, refreshing stale identity-map rows."""
        from app.application.purchase_check_details import (
            PublishedDataErrorCode,
            PublishedPromotionDataError,
        )

        if not candidate_variant_ids:
            return ()
        query = (
            select(PromotionVariant)
            .where(PromotionVariant.id.in_(candidate_variant_ids))
            .options(
                selectinload(PromotionVariant.product_links),
                selectinload(PromotionVariant.requirements),
                selectinload(PromotionVariant.benefits)
                .selectinload(Benefit.reward)
                .selectinload(BenefitReward.product_values),
                selectinload(PromotionVariant.promotion)
                .selectinload(Promotion.source_links)
                .selectinload(PromotionSource.source),
            )
            .execution_options(populate_existing=True)
        )
        try:
            with self.session.no_autoflush:
                return tuple(_check_details(row) for row in self.session.scalars(query))
        except SQLAlchemyError as error:
            raise PromotionPersistenceError("Promotion details query failed") from error
        except PublishedPromotionDataError:
            raise
        except (ValueError, TypeError) as error:
            raise PublishedPromotionDataError(
                code=PublishedDataErrorCode.INVALID_PROJECTION
            ) from error

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


def _check_details(variant):
    from app.application.purchase_check_details import (
        PublishedBenefit,
        PublishedPromotionDetails,
        PublishedRequirement,
    )
    from app.domain.benefits import Benefit as BenefitValue
    from app.domain.requirements import Requirement as RequirementValue
    from app.domain.rewards import (
        FixedAmountReward,
        PercentageReward,
        ProductRewardValue,
        ProductSpecificReward,
        RewardType,
    )

    benefits = []
    for row in sorted(variant.benefits, key=lambda value: value.id):
        reward = None
        if row.reward is not None:
            stored = row.reward
            kind = RewardType(stored.reward_type)
            if kind == RewardType.FIXED_AMOUNT:
                if stored.percentage is not None or stored.product_values:
                    raise ValueError("Invalid fixed reward shape")
                reward = FixedAmountReward(stored.fixed_amount)
            elif kind == RewardType.PERCENTAGE:
                if stored.fixed_amount is not None or stored.product_values:
                    raise ValueError("Invalid percentage reward shape")
                reward = PercentageReward(stored.percentage)
            else:
                if stored.fixed_amount is not None or stored.percentage is not None:
                    raise ValueError("Invalid product reward shape")
                reward = ProductSpecificReward(
                    tuple(
                        ProductRewardValue(value.product_id, value.amount)
                        for value in stored.product_values
                    )
                )
        benefits.append(
            PublishedBenefit(
                row.id, BenefitValue(row.benefit_type, row.name, row.description), reward
            )
        )
    promotion = variant.promotion
    sources = tuple(
        sorted(
            (
                PromotionSourceRecord(
                    link.source_id,
                    link.role,
                    link.source.url,
                    link.source.source_type,
                    link.source.retrieved_at,
                    link.source.verified_at,
                )
                for link in promotion.source_links
            ),
            key=lambda value: (value.role.value, value.source_id),
        )
    )
    return PublishedPromotionDetails(
        promotion.id,
        variant.id,
        promotion.name,
        variant.name,
        PromotionStatus(promotion.status),
        promotion.manufacturer_id,
        variant.retailer_id,
        frozenset(link.product_id for link in variant.product_links),
        promotion.purchase_start_date,
        promotion.purchase_end_date,
        promotion.claim_start_date,
        promotion.claim_end_date,
        promotion.claim_start_offset_days,
        promotion.claim_end_offset_days,
        tuple(benefits),
        tuple(
            PublishedRequirement(row.id, RequirementValue(row.requirement_type, row.description))
            for row in sorted(variant.requirements, key=lambda value: value.id)
        ),
        sources,
    )


@contextmanager
def purchase_check_snapshot(session_factory):
    """Dedicated read-only repeatable-read session shared by identity/candidate/detail reads.

    Always rollback; never flush or commit. Reject reused/pending sessions before SQL.
    """
    from app.application.identity_matching import IdentityResolver
    from app.db.repositories.identity_matching import SqlAlchemyIdentityRepository

    try:
        with session_factory() as session:
            if session.in_transaction() or session.new or session.dirty or session.deleted:
                raise ValueError("Purchase check requires a fresh dedicated session")
            try:
                session.connection(
                    execution_options={
                        "isolation_level": "REPEATABLE READ",
                        "postgresql_readonly": True,
                    }
                )
                with session.no_autoflush:
                    yield (
                        IdentityResolver(SqlAlchemyIdentityRepository(session)),
                        SqlAlchemyPromotionRepository(session),
                    )
            finally:
                session.rollback()
    except SQLAlchemyError:
        raise PromotionPersistenceError("Purchase check snapshot failed") from None
