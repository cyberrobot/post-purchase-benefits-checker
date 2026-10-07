"""Classify completed rule evaluations using an already-determined claim state."""

from dataclasses import dataclass
from enum import StrEnum

from app.domain.eligibility_rules import RuleEvaluation, RuleKind, RuleReasonCode, RuleStatus


class EligibilityClassification(StrEnum):
    ELIGIBLE = "ELIGIBLE"
    POTENTIALLY_ELIGIBLE = "POTENTIALLY_ELIGIBLE"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    CLAIM_NOT_YET_OPEN = "CLAIM_NOT_YET_OPEN"
    EXPIRED = "EXPIRED"


class ClaimWindowStatus(StrEnum):
    OPEN = "open"
    NOT_YET_OPEN = "not_yet_open"
    EXPIRED = "expired"


class EligibilityReasonCode(StrEnum):
    ALL_CONFIGURED_RULES_SATISFIED = "all_configured_rules_satisfied"
    CLAIM_WINDOW_OPEN = "claim_window_open"
    CLAIM_WINDOW_NOT_YET_OPEN = "claim_window_not_yet_open"
    CLAIM_WINDOW_EXPIRED = "claim_window_expired"


@dataclass(frozen=True, slots=True)
class EligibilityReason:
    code: RuleReasonCode | EligibilityReasonCode
    rule_kind: RuleKind | None = None

    def __post_init__(self) -> None:
        if isinstance(self.code, RuleReasonCode):
            if not isinstance(self.rule_kind, RuleKind):
                raise TypeError("Rule reasons require a RuleKind")
        elif isinstance(self.code, EligibilityReasonCode):
            if self.rule_kind is not None:
                raise TypeError("Classification reasons require rule_kind=None")
        else:
            raise TypeError("Reason code must be RuleReasonCode or EligibilityReasonCode")


def _validate_inputs(
    rule_evaluations: tuple[RuleEvaluation, ...], claim_window_status: ClaimWindowStatus
) -> None:
    if not isinstance(rule_evaluations, tuple):
        raise TypeError("Rule evaluations must be a tuple")
    if any(not isinstance(value, RuleEvaluation) for value in rule_evaluations):
        raise TypeError("Rule evaluations must contain RuleEvaluation values")
    if not isinstance(claim_window_status, ClaimWindowStatus):
        raise TypeError("Claim window status must be a ClaimWindowStatus")


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    classification: EligibilityClassification
    reasons: tuple[EligibilityReason, ...]
    rule_evaluations: tuple[RuleEvaluation, ...]
    claim_window_status: ClaimWindowStatus

    def __post_init__(self) -> None:
        _validate_inputs(self.rule_evaluations, self.claim_window_status)
        if not isinstance(self.classification, EligibilityClassification):
            raise TypeError("Classification must be an EligibilityClassification")
        if not isinstance(self.reasons, tuple):
            raise TypeError("Reasons must be a tuple")
        if any(not isinstance(reason, EligibilityReason) for reason in self.reasons):
            raise TypeError("Reasons must contain EligibilityReason values")
        if not self.reasons:
            raise ValueError("An eligibility result requires at least one reason")


def classify_eligibility(
    rule_evaluations: tuple[RuleEvaluation, ...], claim_window_status: ClaimWindowStatus
) -> EligibilityResult:
    """Failures precede unknowns, then claim timing; empty rules impose no restriction.

    Decision reasons preserve input order. When all configured rules are satisfied,
    reasons are always the all-rules-satisfied code followed by the claim-state code.
    Complete evaluations, including non-decisive outcomes, remain on the result.
    """
    _validate_inputs(rule_evaluations, claim_window_status)
    for status, classification in (
        (RuleStatus.NOT_SATISFIED, EligibilityClassification.NOT_ELIGIBLE),
        (RuleStatus.UNKNOWN, EligibilityClassification.POTENTIALLY_ELIGIBLE),
    ):
        reasons = tuple(
            EligibilityReason(evaluation.reason_code, evaluation.kind)
            for evaluation in rule_evaluations
            if evaluation.status == status
        )
        if reasons:
            return EligibilityResult(classification, reasons, rule_evaluations, claim_window_status)

    classification, claim_reason = {
        ClaimWindowStatus.OPEN: (
            EligibilityClassification.ELIGIBLE,
            EligibilityReasonCode.CLAIM_WINDOW_OPEN,
        ),
        ClaimWindowStatus.NOT_YET_OPEN: (
            EligibilityClassification.CLAIM_NOT_YET_OPEN,
            EligibilityReasonCode.CLAIM_WINDOW_NOT_YET_OPEN,
        ),
        ClaimWindowStatus.EXPIRED: (
            EligibilityClassification.EXPIRED,
            EligibilityReasonCode.CLAIM_WINDOW_EXPIRED,
        ),
    }[claim_window_status]
    return EligibilityResult(
        classification,
        (
            EligibilityReason(EligibilityReasonCode.ALL_CONFIGURED_RULES_SATISFIED),
            EligibilityReason(claim_reason),
        ),
        rule_evaluations,
        claim_window_status,
    )
