"""Immutable publication definitions and pure, deterministic completeness checks."""

import re
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from app.domain.benefits import Benefit
from app.domain.claim_windows import FixedClaimWindow, RelativeClaimWindow
from app.domain.promotion_provenance import (
    PromotionProvenanceError,
    PromotionSourceRecord,
    validate_publication_provenance,
)
from app.domain.requirements import Requirement
from app.domain.rewards import (
    FixedAmountReward,
    PercentageReward,
    ProductSpecificReward,
    RewardDefinition,
)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    severity: str = "error"


@dataclass(frozen=True)
class ValidationReport:
    issues: tuple[ValidationIssue, ...]
    persisted: bool = False

    @property
    def can_publish(self) -> bool:
        return self.persisted and not any(i.severity == "error" for i in self.issues)


@dataclass(frozen=True)
class ValidationBenefit:
    benefit: Benefit
    reward: RewardDefinition | None = None
    invalid_reward: bool = False


@dataclass(frozen=True)
class ValidationVariant:
    code: str | None
    name: str | None
    retailer_id: UUID | None
    product_ids: tuple[UUID, ...]
    benefits: tuple[ValidationBenefit, ...]
    requirements: tuple[Requirement, ...] = ()
    product_manufacturers: tuple[tuple[UUID, UUID | None], ...] = ()
    retailer_exists: bool = True


@dataclass(frozen=True)
class ValidationSource:
    source_id: UUID
    role: str
    record: PromotionSourceRecord | None = None


@dataclass(frozen=True)
class PromotionValidationSnapshot:
    manufacturer_id: UUID | None
    name: str | None
    slug: str | None
    purchase_start_date: date | None
    purchase_end_date: date | None
    claim_window: FixedClaimWindow | RelativeClaimWindow | None
    variants: tuple[ValidationVariant, ...]
    sources: tuple[ValidationSource, ...]
    manufacturer_exists: bool = True
    projection_issues: tuple[ValidationIssue, ...] = ()


def validate_definition(
    snapshot: PromotionValidationSnapshot, *, persisted: bool
) -> ValidationReport:
    issues = list(snapshot.projection_issues)

    def add(code, path):
        issues.append(ValidationIssue(code, "/promotion" + path, code.replace("_", " ")))

    if snapshot.manufacturer_id is None:
        add("missing_manufacturer", "/manufacturer_id")
    elif persisted and not snapshot.manufacturer_exists:
        add("manufacturer_not_found", "/manufacturer_id")
    if not snapshot.name or not snapshot.name.strip() or len(snapshot.name) > 255:
        add("missing_promotion_name", "/name")
    if (
        not snapshot.slug
        or len(snapshot.slug) > 255
        or not re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", snapshot.slug)
    ):
        add("invalid_promotion_slug", "/slug")
    if snapshot.purchase_start_date is None and snapshot.purchase_end_date is None:
        add("missing_purchase_window", "/purchase_start_date")
    elif (
        snapshot.purchase_start_date
        and snapshot.purchase_end_date
        and snapshot.purchase_start_date > snapshot.purchase_end_date
    ):
        add("invalid_purchase_window", "/purchase_end_date")
    if snapshot.claim_window is None:
        add("missing_claim_window", "/claim_window")
    elif not isinstance(snapshot.claim_window, (FixedClaimWindow, RelativeClaimWindow)):
        add("invalid_claim_window", "/claim_window")
    if not snapshot.variants:
        add("missing_variant", "/variants")
    codes = set()
    for index, variant in enumerate(snapshot.variants):
        path = f"/variants/{index}"
        if not variant.code or not variant.code.strip() or len(variant.code) > 255:
            add("missing_variant_code", path + "/code")
        elif variant.code in codes:
            add("duplicate_variant_code", path + "/code")
        codes.add(variant.code)
        if persisted and variant.retailer_id and not variant.retailer_exists:
            add("retailer_not_found", path + "/retailer_id")
        if not variant.product_ids:
            add("missing_product", path + "/product_ids")
        if len(set(variant.product_ids)) != len(variant.product_ids):
            add("duplicate_product", path + "/product_ids")
        if persisted:
            manufacturers = dict(variant.product_manufacturers)
            for j, identity in enumerate(variant.product_ids):
                owner = manufacturers.get(identity)
                if owner is None:
                    add("product_not_found", path + f"/product_ids/{j}")
                elif owner != snapshot.manufacturer_id:
                    add("product_manufacturer_mismatch", path + f"/product_ids/{j}")
        if not variant.benefits:
            add("missing_benefit", path + "/benefits")
        for j, value in enumerate(variant.benefits):
            bp = path + f"/benefits/{j}"
            if not value.benefit.name.strip() or len(value.benefit.name) > 255:
                add("missing_benefit_name", bp + "/name")
            if value.invalid_reward or (
                value.reward is not None
                and not isinstance(
                    value.reward, (FixedAmountReward, PercentageReward, ProductSpecificReward)
                )
            ):
                add("invalid_reward", bp + "/reward")
            elif value.benefit.benefit_type == "cashback" and value.reward is None:
                add("missing_cashback_reward", bp + "/reward")
            elif value.benefit.benefit_type != "cashback" and value.reward is not None:
                add("noncashback_reward_not_supported", bp + "/reward")
            if isinstance(value.reward, ProductSpecificReward) and {
                v.product_id for v in value.reward.values
            } != set(variant.product_ids):
                add("product_reward_coverage_mismatch", bp + "/reward/values")
    identities = set()
    for j, source in enumerate(snapshot.sources):
        if source.source_id in identities:
            add("duplicate_source_link", f"/sources/{j}/source_id")
        identities.add(source.source_id)
        if persisted and source.record is None:
            add("source_not_found", f"/sources/{j}/source_id")
    for role in ("primary", "claim"):
        count = sum(s.role == role for s in snapshot.sources)
        if count != 1:
            add(f"{'missing' if count == 0 else 'ambiguous'}_{role}_source", "/sources")
    if persisted:
        try:
            validate_publication_provenance(
                s.record for s in snapshot.sources if s.record is not None
            )
        except PromotionProvenanceError as error:
            if not any(i.code == error.reason_code for i in issues):
                add(error.reason_code, "/sources")
    else:
        issues.append(
            ValidationIssue(
                "unresolved_references",
                "/promotion",
                "Canonical references and curated evidence require database resolution.",
            )
        )
    return ValidationReport(tuple(issues), persisted)


def validate_promotion_for_publication(snapshot: PromotionValidationSnapshot) -> ValidationReport:
    return validate_definition(snapshot, persisted=True)
