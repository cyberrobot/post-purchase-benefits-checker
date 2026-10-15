"""Strict static lookup contracts, distinct from purchase-specific results."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator, model_validator

from app.domain.benefits import BenefitType
from app.domain.promotion_provenance import SourceRole, SourceType
from app.domain.requirements import RequirementType

UUIDText = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$",
    ),
]
DecimalText = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9]+(?:\.[0-9]+)?$")]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class VariantInput(StrictModel):
    promotion_variant_id: UUIDText

    @field_validator(
        "promotion_variant_id", "benefit_id", "source_id", "product_id", check_fields=False
    )
    @classmethod
    def canonical_id(cls, value):
        return str(UUID(value)) if value is not None else None


class BenefitInput(VariantInput):
    benefit_id: UUIDText
    product_id: UUIDText | None = None


class SourceInput(VariantInput):
    source_id: UUIDText


class Reward(StrictModel):
    reward_type: Literal["fixed_amount", "percentage", "product_specific"]
    fixed_amount_gbp: DecimalText | None
    percentage: DecimalText | None
    product_id: UUIDText | None
    product_amount_gbp: DecimalText | None
    product_lookup_status: Literal["not_applicable", "product_id_required", "configured"]

    @model_validator(mode="after")
    def valid_shape(self):
        shape = (
            self.fixed_amount_gbp is not None,
            self.percentage is not None,
            self.product_id is not None,
            self.product_amount_gbp is not None,
            self.product_lookup_status,
        )
        allowed = {
            "fixed_amount": {(True, False, False, False, "not_applicable")},
            "percentage": {(False, True, False, False, "not_applicable")},
            "product_specific": {
                (False, False, False, False, "product_id_required"),
                (False, False, True, True, "configured"),
            },
        }
        if shape not in allowed[self.reward_type]:
            raise ValueError("Invalid static reward shape")
        return self


class IdentityOutput(StrictModel):
    promotion_id: UUIDText
    promotion_variant_id: UUIDText
    promotion_status: Literal["active", "expired"]


class BenefitOutput(IdentityOutput):
    benefit_id: UUIDText
    benefit_type: BenefitType
    name: str
    description: str | None
    reward: Reward | None


class RecordedRequirement(StrictModel):
    requirement_id: UUIDText
    requirement_type: RequirementType
    description: str | None


class RequirementsOutput(IdentityOutput):
    claim_url: str
    requirements_recorded: bool
    requirements: list[RecordedRequirement]

    @model_validator(mode="after")
    def recorded_matches(self):
        if self.requirements_recorded != bool(self.requirements):
            raise ValueError("Inconsistent recorded requirements flag")
        return self


class SourceOutput(IdentityOutput):
    source_id: UUIDText
    role: SourceRole
    url: str
    source_type: SourceType
    retrieved_at: datetime
    verified_at: datetime | None
    is_official_primary_source: bool
    last_verified_at: datetime

    @field_validator("retrieved_at", "verified_at", "last_verified_at")
    @classmethod
    def aware(cls, value):
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Timestamp must have a timezone")
        return value


LOOKUP_SCHEMAS = {
    "get_benefit": (
        BenefitInput,
        BenefitOutput,
        "Inspect stored benefit",
        "Inspect one published benefit and its stored reward definition; "
        "no personal payout calculation.",
    ),
    "get_claim_requirements": (
        VariantInput,
        RequirementsOutput,
        "Get recorded claim requirements",
        "Get recorded requirements and curated claim URL; "
        "an empty list means no requirements recorded.",
    ),
    "get_promotion_source": (
        SourceInput,
        SourceOutput,
        "Inspect linked promotion source",
        "Inspect one linked source and recorded verification metadata; "
        "does not fetch or verify URLs.",
    ),
}
