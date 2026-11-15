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
from app.domain.claim_windows import FixedClaimWindow, RelativeClaimWindow
from app.domain.promotion_identity import public_slug
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
    return validate_published_details(details, variant_id)


def validate_published_details(
    details: PublishedPromotionDetails,
    variant_id: UUID,
    provenance: PublishedProvenance | None = None,
) -> PublishedLookup:
    if not isinstance(details, PublishedPromotionDetails):
        raise PublishedPromotionDataError
    if details.promotion_status not in {PromotionStatus.ACTIVE, PromotionStatus.EXPIRED}:
        raise LookupNotFound
    if not details.product_ids or not details.benefits:
        raise PublishedPromotionDataError
    if details.promotion_variant_id != variant_id:
        raise PublishedPromotionDataError
    try:
        if provenance is None:
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


@dataclass(frozen=True, slots=True)
class PublicIdentity:
    id: UUID
    name: str


@dataclass(frozen=True, slots=True)
class PublicProduct:
    id: UUID
    name: str
    model_number: str | None


@dataclass(frozen=True, slots=True)
class PublicVariant:
    details: PublishedPromotionDetails
    code: str
    products: tuple[PublicProduct, ...]
    retailer: PublicIdentity | None


@dataclass(frozen=True, slots=True)
class PublicPromotion:
    manufacturer: PublicIdentity
    manufacturer_slug: str
    promotion_slug: str
    variants: tuple[PublicVariant, ...]


class PublicPromotionRepository(Protocol):
    def load_public_promotion(
        self, manufacturer_slug: str, promotion_slug: str
    ) -> PublicPromotion | None: ...


def get_public_promotion(
    repository: PublicPromotionRepository, manufacturer_slug: str, promotion_slug: str
) -> tuple[PublicPromotion, PublishedProvenance, FixedClaimWindow | RelativeClaimWindow | None]:
    if public_slug(manufacturer_slug, promotion_slug) is None:
        raise LookupNotFound
    promotion = repository.load_public_promotion(manufacturer_slug, promotion_slug)
    if promotion is None:
        raise LookupNotFound
    if not promotion.variants:
        raise PublishedPromotionDataError
    primary = promotion.variants[0].details
    provenance = None
    try:
        for variant in promotion.variants:
            detail = variant.details
            if (
                detail.promotion_id != primary.promotion_id
                or detail.manufacturer_id != promotion.manufacturer.id
                or detail.sources != primary.sources
                or {product.id for product in variant.products} != detail.product_ids
                or (variant.retailer.id if variant.retailer else None) != detail.retailer_id
            ):
                raise PublishedPromotionDataError
            provenance = validate_published_details(
                detail, detail.promotion_variant_id, provenance
            ).provenance
        if (
            primary.purchase_start_date is not None
            and primary.purchase_end_date is not None
            and primary.purchase_start_date > primary.purchase_end_date
        ):
            raise PublishedPromotionDataError
        fixed = (primary.claim_start_date, primary.claim_end_date)
        relative = (primary.claim_start_offset_days, primary.claim_end_offset_days)
        window = None
        if any(value is not None for value in fixed):
            if any(value is not None for value in relative):
                raise PublishedPromotionDataError
            window = FixedClaimWindow(*fixed, primary.claim_min_wait_days)
        elif primary.claim_min_wait_days is not None:
            raise PublishedPromotionDataError
        elif any(value is not None for value in relative):
            window = RelativeClaimWindow(*relative)
    except (ValueError, TypeError) as error:
        raise PublishedPromotionDataError from error
    assert provenance is not None
    return promotion, provenance, window
