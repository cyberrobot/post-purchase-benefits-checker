"""Static public promotion contract."""

import ipaddress
import re
from datetime import date
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.application.promotion_details import PublicPromotion
from app.domain.benefits import BenefitType
from app.domain.claim_windows import FixedClaimWindow, RelativeClaimWindow
from app.domain.promotion_identity import PUBLIC_SLUG_PATTERN, SLUG_PATTERN, is_slug, public_slug
from app.domain.promotion_provenance import (
    PublishedProvenance,
    SourceRole,
    SourceType,
    is_valid_source_url,
)
from app.domain.requirements import RequirementType
from app.domain.rewards import FixedAmountReward, PercentageReward, ProductSpecificReward


def checked_slug(value: str) -> str:
    if not is_slug(value):
        raise ValueError("Invalid slug")
    return value


def checked_url(value: str) -> str:
    if not is_valid_source_url(value) or "\\" in value:
        raise ValueError("Invalid source URL")
    hostname = urlsplit(value).hostname
    if not hostname or any(char in hostname for char in "%<>^|"):
        raise ValueError("Invalid source host")
    # urllib accepts out-of-range dotted IPv4 strings as hostnames, but browsers reject
    # them as invalid URL hosts. Keep the public JSON boundary consistent with browsers.
    if re.fullmatch(r"[0-9.]+", hostname):
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            raise ValueError("Invalid source host") from None
    return value


Slug = Annotated[
    str, StringConstraints(pattern=SLUG_PATTERN, max_length=255), AfterValidator(checked_slug)
]
DecimalString = Annotated[str, StringConstraints(pattern=r"^[0-9]+(\.[0-9]+)?$")]
SourceUrl = Annotated[str, AfterValidator(checked_url)]
Days = Annotated[int, Field(ge=0)]
Name = Annotated[str, StringConstraints(min_length=1)]


class PublicModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, from_attributes=True)


class Identity(PublicModel):
    id: UUID
    name: Name


class Manufacturer(Identity):
    slug: Slug


class Product(Identity):
    model_number: str | None


class PurchaseWindow(PublicModel):
    starts_on: date | None
    ends_on: date | None


class FixedWindow(PublicModel):
    kind: Literal["fixed"]
    opens_on: date
    deadline_on: date
    minimum_days_after_purchase: Days | None


class RelativeWindow(PublicModel):
    kind: Literal["relative"]
    opens_after_purchase_days: Days
    deadline_after_purchase_days: Days


class Amount(PublicModel):
    kind: Literal["fixed_amount"]
    amount_gbp: DecimalString


class Percentage(PublicModel):
    kind: Literal["percentage"]
    percentage: DecimalString


class ProductValue(PublicModel):
    product_id: UUID
    amount_gbp: DecimalString


class ProductAmounts(PublicModel):
    kind: Literal["product_specific"]
    values: list[ProductValue] = Field(min_length=1)


Reward = Annotated[Amount | Percentage | ProductAmounts, Field(discriminator="kind")]
ClaimWindow = Annotated[FixedWindow | RelativeWindow, Field(discriminator="kind")]


class Benefit(PublicModel):
    benefit_id: UUID
    benefit_type: BenefitType
    name: Name
    description: str | None
    reward: Reward | None


class Requirement(PublicModel):
    requirement_id: UUID
    requirement_type: RequirementType
    description: str | None


class Variant(PublicModel):
    promotion_variant_id: UUID
    code: Name
    name: str | None
    retailer: Identity | None
    products: list[Product] = Field(min_length=1)
    benefits: list[Benefit] = Field(min_length=1)
    requirements: list[Requirement]


class Provenance(PublicModel):
    official_source_url: SourceUrl
    claim_url: SourceUrl
    last_verified_at: AwareDatetime


class Source(PublicModel):
    source_id: UUID
    role: SourceRole
    url: SourceUrl
    source_type: SourceType
    retrieved_at: AwareDatetime
    verified_at: AwareDatetime | None


class PromotionDetails(PublicModel):
    promotion_id: UUID
    public_slug: Annotated[str, StringConstraints(pattern=PUBLIC_SLUG_PATTERN, max_length=512)]
    name: Name
    status: Literal["active", "expired"]
    manufacturer: Manufacturer
    purchase_window: PurchaseWindow
    claim_window: ClaimWindow | None
    variants: list[Variant] = Field(min_length=1)
    provenance: Provenance
    sources: list[Source] = Field(min_length=2)


def map_reward(reward):
    if isinstance(reward, FixedAmountReward):
        return Amount(kind="fixed_amount", amount_gbp=format(reward.amount, "f"))
    if isinstance(reward, PercentageReward):
        return Percentage(kind="percentage", percentage=format(reward.percentage, "f"))
    if isinstance(reward, ProductSpecificReward):
        return ProductAmounts(
            kind="product_specific",
            values=[
                ProductValue(product_id=value.product_id, amount_gbp=format(value.amount, "f"))
                for value in sorted(reward.values, key=lambda value: value.product_id)
            ],
        )
    return None


def map_promotion(
    promotion: PublicPromotion,
    provenance: PublishedProvenance,
    window: FixedClaimWindow | RelativeClaimWindow | None,
) -> PromotionDetails:
    first = promotion.variants[0].details
    claim: ClaimWindow | None = None
    if isinstance(window, FixedClaimWindow):
        claim = FixedWindow(
            kind="fixed",
            opens_on=window.start_date,
            deadline_on=window.end_date,
            minimum_days_after_purchase=window.minimum_days_after_purchase,
        )
    if isinstance(window, RelativeClaimWindow):
        claim = RelativeWindow(
            kind="relative",
            opens_after_purchase_days=window.start_offset_days,
            deadline_after_purchase_days=window.end_offset_days,
        )
    return PromotionDetails(
        promotion_id=first.promotion_id,
        public_slug=public_slug(promotion.manufacturer_slug, promotion.promotion_slug),
        name=first.promotion_name,
        status=first.promotion_status.value,
        manufacturer=Manufacturer(
            id=promotion.manufacturer.id,
            name=promotion.manufacturer.name,
            slug=promotion.manufacturer_slug,
        ),
        purchase_window=PurchaseWindow(
            starts_on=first.purchase_start_date, ends_on=first.purchase_end_date
        ),
        claim_window=claim,
        variants=[
            Variant(
                promotion_variant_id=variant.details.promotion_variant_id,
                code=variant.code,
                name=variant.details.variant_name,
                retailer=Identity.model_validate(variant.retailer) if variant.retailer else None,
                products=[Product.model_validate(product) for product in variant.products],
                benefits=[
                    Benefit(
                        benefit_id=item.benefit_id,
                        benefit_type=item.benefit.benefit_type,
                        name=item.benefit.name,
                        description=item.benefit.description,
                        reward=map_reward(item.reward),
                    )
                    for item in variant.details.benefits
                ],
                requirements=[
                    Requirement(
                        requirement_id=item.requirement_id,
                        requirement_type=item.requirement.requirement_type,
                        description=item.requirement.description,
                    )
                    for item in variant.details.requirements
                ],
            )
            for variant in promotion.variants
        ],
        provenance=Provenance(
            official_source_url=provenance.official_source_url,
            claim_url=provenance.claim_url,
            last_verified_at=provenance.verified_at,
        ),
        sources=[Source.model_validate(source) for source in first.sources],
    )
