"""Explicit v1 wire contracts; no eligibility calculation belongs here."""

import re
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator

from app.application.purchase_check_details import NoMatchReason, RewardUnavailableReason
from app.domain.benefits import BenefitType
from app.domain.eligibility_result import (
    ClaimWindowStatus,
    EligibilityClassification,
    EligibilityReasonCode,
)
from app.domain.eligibility_rules import RuleKind, RuleReasonCode, RuleStatus
from app.domain.identity_normalisation import normalise_identifier, normalise_text
from app.domain.promotion_lifecycle import PromotionStatus
from app.domain.promotion_provenance import SourceRole, SourceType
from app.domain.requirements import RequirementType

PRICE_PATTERN = r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,2})?$"


class PurchaseRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "brand": "Example Brand",
                "model": "MODEL-123",
                "retailer": "Example Retailer",
                "purchase_date": "2026-10-01",
                "purchase_price": "799.99",
            }
        },
    )
    brand: StrictStr = Field(max_length=255)
    model: StrictStr = Field(max_length=255)
    retailer: StrictStr = Field(max_length=255)
    purchase_date: StrictStr = Field(pattern=r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
    purchase_price: StrictStr | None = Field(default=None, pattern=PRICE_PATTERN)

    @field_validator("brand", "model", "retailer")
    @classmethod
    def identity(cls, value, info):
        (normalise_identifier if info.field_name == "model" else normalise_text)(value)
        return value

    @field_validator("purchase_date")
    @classmethod
    def calendar_date(cls, value):
        date.fromisoformat(value)
        return value

    @field_validator("purchase_price")
    @classmethod
    def price(cls, value):
        if value is not None and re.fullmatch(PRICE_PATTERN, value) is None:
            raise ValueError("Invalid GBP wire amount")
        return value


class Identity(BaseModel):
    manufacturer_id: UUID
    retailer_id: UUID
    product_id: UUID


class UnresolvedIdentity(BaseModel):
    field: Literal["brand", "model", "retailer"]
    status: Literal["not_found", "ambiguous"]
    candidate_ids: list[UUID]


class Reason(BaseModel):
    code: RuleReasonCode | EligibilityReasonCode
    rule_kind: RuleKind | None


class Rule(BaseModel):
    kind: RuleKind
    status: RuleStatus
    reason_code: RuleReasonCode


class Eligibility(BaseModel):
    classification: EligibilityClassification
    reasons: list[Reason]
    rule_evaluations: list[Rule]
    claim_window_status: ClaimWindowStatus | None


class ClaimWindow(BaseModel):
    status: ClaimWindowStatus
    opens_on: date
    deadline_on: date


class Benefit(BaseModel):
    benefit_id: UUID
    benefit_type: BenefitType
    name: str
    description: str | None
    cashback_reward_gbp: str | None
    reward_unavailable_reason: RewardUnavailableReason | None
    reward_unavailable_explanation: str | None


class Requirement(BaseModel):
    requirement_type: RequirementType
    description: str | None


class Provenance(BaseModel):
    official_source_url: str
    source_type: SourceType
    retrieved_at: datetime
    verified_at: datetime
    claim_url: str


class Source(BaseModel):
    source_id: UUID
    role: SourceRole
    url: str
    source_type: SourceType
    retrieved_at: datetime
    verified_at: datetime | None


class Promotion(BaseModel):
    promotion_id: UUID
    promotion_variant_id: UUID
    promotion_name: str
    variant_name: str | None
    promotion_status: PromotionStatus
    eligibility: Eligibility
    claim_window: ClaimWindow | None
    benefits: list[Benefit]
    requirements: list[Requirement]
    provenance: Provenance
    sources: list[Source]
    explanation: list[str]


class ResolvedResponse(BaseModel):
    outcome: Literal["resolved"]
    evaluation_date: date
    resolved_identity: Identity
    promotions: list[Promotion]
    no_match_reason: NoMatchReason | None
    explanation: list[str]


class UnresolvedResponse(BaseModel):
    outcome: Literal["unresolved_identity"]
    evaluation_date: date
    unresolved_identity: UnresolvedIdentity
    explanation: list[str]


CheckResponse = Annotated[ResolvedResponse | UnresolvedResponse, Field(discriminator="outcome")]


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str
    request_id: UUID


def map_result(result, evaluation_date):
    from app.application.promotion_candidate_matching import UnresolvedPurchaseIdentity

    if isinstance(result, UnresolvedPurchaseIdentity):
        return UnresolvedResponse(
            outcome="unresolved_identity",
            evaluation_date=evaluation_date,
            unresolved_identity=UnresolvedIdentity(
                field=result.field, status=result.status, candidate_ids=list(result.candidate_ids)
            ),
            explanation=[result.explanation],
        )
    return ResolvedResponse(
        outcome="resolved",
        evaluation_date=evaluation_date,
        resolved_identity=Identity.model_validate(result.resolved_identity, from_attributes=True),
        promotions=[
            Promotion(
                promotion_id=p.promotion_id,
                promotion_variant_id=p.promotion_variant_id,
                promotion_name=p.promotion_name,
                variant_name=p.variant_name,
                promotion_status=p.promotion_status,
                eligibility=Eligibility(
                    classification=p.eligibility.classification,
                    reasons=[
                        Reason.model_validate(x, from_attributes=True)
                        for x in p.eligibility.reasons
                    ],
                    rule_evaluations=[
                        Rule.model_validate(x, from_attributes=True)
                        for x in p.eligibility.rule_evaluations
                    ],
                    claim_window_status=p.eligibility.claim_window_status,
                ),
                claim_window=ClaimWindow.model_validate(p.claim_window, from_attributes=True)
                if p.claim_window
                else None,
                benefits=[
                    Benefit(
                        benefit_id=b.benefit_id,
                        benefit_type=b.benefit.benefit_type,
                        name=b.benefit.name,
                        description=b.benefit.description,
                        cashback_reward_gbp=format(b.cashback_reward_gbp, "f")
                        if b.cashback_reward_gbp is not None
                        else None,
                        reward_unavailable_reason=b.reward_unavailable_reason,
                        reward_unavailable_explanation=b.reward_unavailable_explanation,
                    )
                    for b in p.benefits
                ],
                requirements=[
                    Requirement.model_validate(x, from_attributes=True) for x in p.requirements
                ],
                provenance=Provenance.model_validate(p.provenance, from_attributes=True),
                sources=[Source.model_validate(x, from_attributes=True) for x in p.sources],
                explanation=list(p.explanation),
            )
            for p in result.promotions
        ],
        no_match_reason=result.no_match_reason,
        explanation=list(result.explanation),
    )
