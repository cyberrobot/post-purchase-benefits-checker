"""Independent, read-only published detail queries; no eligibility evaluation."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.application.purchase_check_details import (
    PublishedBenefit,
    PublishedPromotionDataError,
    PublishedPromotionDetails,
)
from app.domain.promotion_lifecycle import PromotionStatus
from app.domain.promotion_provenance import (
    PromotionProvenanceError,
    PromotionSourceRecord,
    PublishedProvenance,
    is_valid_source_url,
    validate_publication_provenance,
)
from app.domain.rewards import ProductSpecificReward


class LookupNotFound(ValueError):
    pass


class InvalidLookupRequest(ValueError):
    pass


class PublishedDetailsRepository(Protocol):
    def load_published_variant(self, variant_id: UUID) -> PublishedPromotionDetails | None: ...


@dataclass(frozen=True, slots=True)
class PublishedLookup:
    details: PublishedPromotionDetails
    provenance: PublishedProvenance

    def benefit(self, benefit_id: UUID, product_id: UUID | None = None) -> PublishedBenefit:
        benefit = next((b for b in self.details.benefits if b.benefit_id == benefit_id), None)
        if benefit is None:
            raise LookupNotFound
        if product_id is not None:
            if not isinstance(benefit.reward, ProductSpecificReward):
                raise InvalidLookupRequest
            if product_id not in self.details.product_ids:
                raise LookupNotFound
        return benefit

    def source(self, source_id: UUID) -> PromotionSourceRecord:
        source = next((s for s in self.details.sources if s.source_id == source_id), None)
        if source is None:
            raise LookupNotFound
        return source


def get_published_details(
    repository: PublishedDetailsRepository, variant_id: UUID
) -> PublishedLookup:
    details = repository.load_published_variant(variant_id)
    if details is None:
        raise LookupNotFound
    if not isinstance(details, PublishedPromotionDetails):
        raise PublishedPromotionDataError
    if details.promotion_status not in {PromotionStatus.ACTIVE, PromotionStatus.EXPIRED}:
        raise LookupNotFound
    if not details.product_ids or not details.benefits:
        raise PublishedPromotionDataError
    if details.promotion_variant_id != variant_id:
        raise PublishedPromotionDataError
    try:
        provenance = validate_publication_provenance(details.sources)
        for source in details.sources:
            if not isinstance(source.source_id, UUID) or not is_valid_source_url(source.url):
                raise PublishedPromotionDataError
            timestamps = (source.retrieved_at,) + (
                (source.verified_at,) if source.verified_at is not None else ()
            )
            for timestamp in timestamps:
                if (
                    not isinstance(timestamp, datetime)
                    or timestamp.tzinfo is None
                    or (timestamp.utcoffset() is None)
                ):
                    raise PublishedPromotionDataError
            if source.verified_at is not None and source.verified_at < source.retrieved_at:
                raise PublishedPromotionDataError
        if len({s.source_id for s in details.sources}) != len(details.sources):
            raise PublishedPromotionDataError
        for benefit in details.benefits:
            if benefit.benefit.benefit_type != "cashback" and benefit.reward is not None:
                raise PublishedPromotionDataError
            if isinstance(benefit.reward, ProductSpecificReward):
                configured = {v.product_id for v in benefit.reward.values}
                if configured != details.product_ids:
                    raise PublishedPromotionDataError
    except (PromotionProvenanceError, ValueError, TypeError) as error:
        raise PublishedPromotionDataError from error
    return PublishedLookup(details, provenance)
