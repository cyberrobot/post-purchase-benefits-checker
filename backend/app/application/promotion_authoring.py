"""Strict, bounded v1 candidate format; no persistence or publication approval."""

import json
import re
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.domain.benefits import Benefit, BenefitType
from app.domain.claim_windows import FixedClaimWindow, RelativeClaimWindow
from app.domain.promotion_provenance import SourceRole
from app.domain.promotion_validation import (
    PromotionValidationSnapshot,
    ValidationBenefit,
    ValidationIssue,
    ValidationReport,
    ValidationSource,
    ValidationVariant,
    validate_definition,
)
from app.domain.requirements import Requirement, RequirementType
from app.domain.rewards import (
    FixedAmountReward,
    PercentageReward,
    ProductRewardValue,
    ProductSpecificReward,
)

MAX_DOCUMENT_BYTES = 262144
MAX_DEPTH = 12
Name = Annotated[str, Field(strict=True, max_length=255)]
Text = Annotated[str, Field(strict=True, max_length=2000)]


class CandidateModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FixedWindow(CandidateModel):
    type: Literal["fixed"]
    start_date: date
    end_date: date

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def iso_date(cls, value):
        if type(value) is not str or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Expected ISO calendar date")
        return value


class RelativeWindow(CandidateModel):
    type: Literal["relative"]
    start_offset_days: Annotated[int, Field(strict=True, ge=0, le=3652058)]
    end_offset_days: Annotated[int, Field(strict=True, ge=0, le=3652058)]


class FixedReward(CandidateModel):
    type: Literal["fixed_amount"]
    amount_gbp: Annotated[
        str, Field(strict=True, max_length=64, pattern=r"^[0-9]+(\.[0-9]{1,2})?$")
    ]

    @field_validator("amount_gbp")
    @classmethod
    def positive(cls, value):
        FixedAmountReward(Decimal(value))
        return value


class Percentage(CandidateModel):
    type: Literal["percentage"]
    percentage: Annotated[
        str, Field(strict=True, max_length=64, pattern=r"^[0-9]+(\.[0-9]{1,4})?$")
    ]

    @field_validator("percentage")
    @classmethod
    def positive(cls, value):
        PercentageReward(Decimal(value))
        return value


class ProductValue(CandidateModel):
    product_id: UUID
    amount_gbp: Annotated[
        str, Field(strict=True, max_length=64, pattern=r"^[0-9]+(\.[0-9]{1,2})?$")
    ]

    @field_validator("amount_gbp")
    @classmethod
    def positive(cls, value):
        return FixedReward.positive(value)


class ProductReward(CandidateModel):
    type: Literal["product_specific"]
    values: Annotated[list[ProductValue], Field(strict=True, max_length=200)]


Reward = Annotated[FixedReward | Percentage | ProductReward, Field(discriminator="type")]
Window = Annotated[FixedWindow | RelativeWindow, Field(discriminator="type")]


def _error_path(loc: tuple[object, ...]) -> str:
    """Convert Pydantic locations to JSON Pointers, removing union tags only at union sites."""
    parts = [str(part) for part in loc]
    window_prefix = ("promotion", "claim_window")
    if (
        len(parts) > len(window_prefix)
        and tuple(parts[: len(window_prefix)]) == window_prefix
        and parts[len(window_prefix)] in {"fixed", "relative"}
    ):
        del parts[len(window_prefix)]

    if (
        len(parts) > 6
        and parts[0] == "promotion"
        and parts[1] == "variants"
        and parts[2].isdigit()
        and parts[3] == "benefits"
        and parts[4].isdigit()
        and parts[5] == "reward"
        and parts[6] in {"fixed_amount", "percentage", "product_specific"}
    ):
        del parts[6]

    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


class CandidateBenefit(CandidateModel):
    type: BenefitType
    name: Name
    description: Text | None = None
    reward: Reward | None = None


class CandidateRequirement(CandidateModel):
    type: RequirementType
    description: Text | None = None


class CandidateVariant(CandidateModel):
    code: Name | None = None
    name: Name | None = None
    retailer_id: UUID | None
    product_ids: Annotated[list[UUID], Field(strict=True, max_length=200)] = Field(
        default_factory=list
    )
    benefits: Annotated[list[CandidateBenefit], Field(strict=True, max_length=20)] = Field(
        default_factory=list
    )
    requirements: Annotated[list[CandidateRequirement], Field(strict=True, max_length=30)] = Field(
        default_factory=list
    )


class CandidateSource(CandidateModel):
    source_id: UUID
    role: SourceRole


class CandidatePromotionBody(CandidateModel):
    manufacturer_id: UUID | None = None
    name: Name | None = None
    slug: Name | None = None
    purchase_start_date: date | None = None
    purchase_end_date: date | None = None
    claim_window: Window | None = None
    variants: Annotated[list[CandidateVariant], Field(strict=True, max_length=50)] = Field(
        default_factory=list
    )
    sources: Annotated[list[CandidateSource], Field(strict=True, max_length=30)] = Field(
        default_factory=list
    )

    @field_validator("purchase_start_date", "purchase_end_date", mode="before")
    @classmethod
    def iso_date(cls, value):
        return None if value is None else FixedWindow.iso_date(value)


class CandidatePromotionV1(CandidateModel):
    schema_version: Literal[1]
    promotion: CandidatePromotionBody

    @field_validator("schema_version", mode="before")
    @classmethod
    def version(cls, value):
        if type(value) is not int or value != 1:
            raise ValueError("Unsupported version")
        return value


class CandidateInputError(ValueError):
    def __init__(self, report: ValidationReport):
        self.report = report
        super().__init__("Candidate promotion input rejected")


def parse_candidate_promotion(raw: Mapping[str, object]) -> CandidatePromotionV1:
    nodes = 0

    def bounded(value, depth=0):
        nonlocal nodes
        nodes += 1
        if nodes > 10000 or (isinstance(value, str) and len(value) > MAX_DOCUMENT_BYTES):
            raise ValueError
        if depth > MAX_DEPTH:
            raise ValueError
        if isinstance(value, Mapping):
            for key, item in value.items():
                if type(key) is not str:
                    raise ValueError
                bounded(item, depth + 1)
        elif isinstance(value, list):
            for item in value:
                bounded(item, depth + 1)
        elif value is not None and type(value) not in (str, int, float, bool):
            raise ValueError

    try:
        bounded(raw)
        if len(json.dumps(raw, allow_nan=False).encode()) > MAX_DOCUMENT_BYTES:
            raise ValueError
    except (TypeError, ValueError, RecursionError):
        raise CandidateInputError(
            ValidationReport(
                (ValidationIssue("invalid_document", "", "Document must be bounded JSON data."),)
            )
        ) from None
    try:
        candidate = CandidatePromotionV1.model_validate(raw)
    except ValidationError as error:
        issues = []
        for item in error.errors(include_input=False, include_context=False, include_url=False):
            loc = item["loc"]
            code = (
                "unsupported_field" if item["type"] == "extra_forbidden" else "invalid_field_type"
            )
            if loc == ("schema_version",):
                code = "unsupported_schema_version"
            path = _error_path(loc)
            issues.append(ValidationIssue(code, path, "Invalid candidate field."))
        raise CandidateInputError(ValidationReport(tuple(issues))) from None
    if sum(len(v.product_ids) for v in candidate.promotion.variants) > 200:
        raise CandidateInputError(
            ValidationReport(
                (
                    ValidationIssue(
                        "too_many_products",
                        "/promotion/variants",
                        "At most 200 product references are allowed.",
                    ),
                )
            )
        )
    return candidate


def validate_candidate_promotion(candidate: CandidatePromotionV1) -> ValidationReport:
    body = candidate.promotion
    issues = []
    window = None
    if body.claim_window:
        try:
            w = body.claim_window
            window = (
                FixedClaimWindow(w.start_date, w.end_date)
                if isinstance(w, FixedWindow)
                else RelativeClaimWindow(w.start_offset_days, w.end_offset_days)
            )
        except (ValueError, TypeError):
            issues.append(
                ValidationIssue(
                    "invalid_claim_window", "/promotion/claim_window", "Invalid claim window."
                )
            )
    variants = []
    for variant in body.variants:
        benefits = []
        for benefit in variant.benefits:
            reward = None
            invalid = False
            try:
                r = benefit.reward
                if isinstance(r, FixedReward):
                    reward = FixedAmountReward(Decimal(r.amount_gbp))
                elif isinstance(r, Percentage):
                    reward = PercentageReward(Decimal(r.percentage))
                elif isinstance(r, ProductReward):
                    reward = ProductSpecificReward(
                        tuple(
                            ProductRewardValue(v.product_id, Decimal(v.amount_gbp))
                            for v in r.values
                        )
                    )
            except (ValueError, TypeError):
                invalid = True
            benefits.append(
                ValidationBenefit(
                    Benefit(benefit.type, benefit.name, benefit.description), reward, invalid
                )
            )
        variants.append(
            ValidationVariant(
                variant.code,
                variant.name,
                variant.retailer_id,
                tuple(variant.product_ids),
                tuple(benefits),
                tuple(Requirement(r.type, r.description) for r in variant.requirements),
            )
        )
    snapshot = PromotionValidationSnapshot(
        body.manufacturer_id,
        body.name,
        body.slug,
        body.purchase_start_date,
        body.purchase_end_date,
        window,
        tuple(variants),
        tuple(ValidationSource(s.source_id, s.role) for s in body.sources),
        projection_issues=tuple(issues),
    )
    return validate_definition(snapshot, persisted=False)
