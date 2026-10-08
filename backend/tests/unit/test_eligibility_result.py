from dataclasses import FrozenInstanceError, fields, replace
from datetime import date
from decimal import Decimal
from itertools import product
from uuid import UUID

import pytest

from app.domain.eligibility_result import (
    ClaimWindowStatus,
    EligibilityClassification,
    EligibilityReason,
    EligibilityReasonCode,
    EligibilityResult,
    classify_eligibility,
)
from app.domain.eligibility_rules import (
    CountryRule,
    PromotionEligibilityRules,
    PurchaseChannelRule,
    PurchaseEligibilityFacts,
    PurchasePriceRule,
    RuleEvaluation,
    RuleKind,
    RuleReasonCode,
    RuleStatus,
    evaluate_eligibility_rules,
)
from app.domain.identity_normalisation import PurchaseChannel
from app.domain.promotion_lifecycle import PromotionStatus

CLAIM_CASES = (
    (
        ClaimWindowStatus.OPEN,
        EligibilityClassification.ELIGIBLE,
        EligibilityReasonCode.CLAIM_WINDOW_OPEN,
    ),
    (
        ClaimWindowStatus.NOT_YET_OPEN,
        EligibilityClassification.CLAIM_NOT_YET_OPEN,
        EligibilityReasonCode.CLAIM_WINDOW_NOT_YET_OPEN,
    ),
    (
        ClaimWindowStatus.EXPIRED,
        EligibilityClassification.EXPIRED,
        EligibilityReasonCode.CLAIM_WINDOW_EXPIRED,
    ),
)
RULE_CASES = (
    (
        RuleKind.PURCHASE_CHANNEL,
        (
            RuleReasonCode.PURCHASE_CHANNEL_MATCH,
            RuleReasonCode.PURCHASE_CHANNEL_MISMATCH,
            RuleReasonCode.PURCHASE_CHANNEL_UNKNOWN,
        ),
    ),
    (
        RuleKind.PURCHASE_PRICE,
        (
            RuleReasonCode.PURCHASE_PRICE_MATCH,
            RuleReasonCode.PURCHASE_PRICE_BELOW_MINIMUM,
            RuleReasonCode.PURCHASE_PRICE_UNKNOWN,
        ),
    ),
    (
        RuleKind.COUNTRY,
        (
            RuleReasonCode.COUNTRY_MATCH,
            RuleReasonCode.COUNTRY_MISMATCH,
            RuleReasonCode.COUNTRY_UNKNOWN,
        ),
    ),
)
SATISFIED = RuleEvaluation(RuleKind.RETAILER, RuleStatus.SATISFIED, RuleReasonCode.RETAILER_MATCH)


def test_stable_enum_contracts():
    assert [(member.name, member.value) for member in EligibilityClassification] == [
        ("ELIGIBLE", "ELIGIBLE"),
        ("POTENTIALLY_ELIGIBLE", "POTENTIALLY_ELIGIBLE"),
        ("NOT_ELIGIBLE", "NOT_ELIGIBLE"),
        ("CLAIM_NOT_YET_OPEN", "CLAIM_NOT_YET_OPEN"),
        ("EXPIRED", "EXPIRED"),
    ]
    assert [(member.name, member.value) for member in ClaimWindowStatus] == [
        ("OPEN", "open"),
        ("NOT_YET_OPEN", "not_yet_open"),
        ("EXPIRED", "expired"),
    ]
    assert [member.value for member in EligibilityReasonCode] == [
        "all_configured_rules_satisfied",
        "claim_window_open",
        "claim_window_not_yet_open",
        "claim_window_expired",
        "claim_window_unspecified",
    ]


@pytest.mark.parametrize("claim,classification,claim_reason", CLAIM_CASES)
@pytest.mark.parametrize(
    "evaluations",
    [
        (),
        (SATISFIED,),
        (
            SATISFIED,
            RuleEvaluation(RuleKind.PRODUCT, RuleStatus.SATISFIED, RuleReasonCode.PRODUCT_MATCH),
        ),
    ],
)
def test_satisfied_or_empty_rules_use_supplied_claim_state(
    evaluations, claim, classification, claim_reason
):
    result = classify_eligibility(evaluations, claim)
    assert result.classification is classification
    assert result.reasons == (
        EligibilityReason(EligibilityReasonCode.ALL_CONFIGURED_RULES_SATISFIED),
        EligibilityReason(claim_reason),
    )
    assert result.rule_evaluations is evaluations
    assert result.claim_window_status is claim


@pytest.mark.parametrize("claim,claim_classification,claim_reason", CLAIM_CASES)
@pytest.mark.parametrize("statuses", list(product(RuleStatus, repeat=3)))
def test_every_rule_status_combination_and_claim_state(
    statuses, claim, claim_classification, claim_reason
):
    evaluations = tuple(
        RuleEvaluation(kind, status, codes[list(RuleStatus).index(status)])
        for status, (kind, codes) in zip(statuses, RULE_CASES, strict=True)
    )
    result = classify_eligibility(evaluations, claim)
    if RuleStatus.NOT_SATISFIED in statuses:
        expected_classification = EligibilityClassification.NOT_ELIGIBLE
        decisive_status = RuleStatus.NOT_SATISFIED
    elif RuleStatus.UNKNOWN in statuses:
        expected_classification = EligibilityClassification.POTENTIALLY_ELIGIBLE
        decisive_status = RuleStatus.UNKNOWN
    else:
        expected_classification = claim_classification
        decisive_status = None
    assert result.classification is expected_classification
    if decisive_status is not None:
        decisive = tuple(e for e in evaluations if e.status is decisive_status)
        assert result.reasons == tuple(EligibilityReason(e.reason_code, e.kind) for e in decisive)
        for reason, evaluation in zip(result.reasons, decisive, strict=True):
            assert reason.code is evaluation.reason_code
    else:
        assert result.reasons == (
            EligibilityReason(EligibilityReasonCode.ALL_CONFIGURED_RULES_SATISFIED),
            EligibilityReason(claim_reason),
        )
    assert result.rule_evaluations is evaluations
    assert result.claim_window_status is claim
    equivalent = tuple(replace(e) for e in evaluations)
    assert classify_eligibility(equivalent, claim) == result


@pytest.mark.parametrize("status", [RuleStatus.NOT_SATISFIED, RuleStatus.UNKNOWN])
@pytest.mark.parametrize("claim", list(ClaimWindowStatus))
def test_single_decisive_rule(status, claim):
    code = (
        RuleReasonCode.PURCHASE_PRICE_UNKNOWN
        if status is RuleStatus.UNKNOWN
        else RuleReasonCode.PURCHASE_PRICE_BELOW_MINIMUM
    )
    evaluation = RuleEvaluation(RuleKind.PURCHASE_PRICE, status, code)
    result = classify_eligibility((evaluation,), claim)
    assert result.classification is (
        EligibilityClassification.POTENTIALLY_ELIGIBLE
        if status is RuleStatus.UNKNOWN
        else EligibilityClassification.NOT_ELIGIBLE
    )
    assert result.reasons == (EligibilityReason(code, RuleKind.PURCHASE_PRICE),)


def test_consumes_pr10_outcomes_in_evaluation_order_without_re_evaluation():
    identity = UUID(int=1)
    facts = PurchaseEligibilityFacts(identity, identity, identity, date(2024, 2, 29))
    rules = PromotionEligibilityRules(
        country=CountryRule({"GB"}),
        purchase_price=PurchasePriceRule(Decimal("10")),
        purchase_channel=PurchaseChannelRule({PurchaseChannel.ONLINE}),
    )
    evaluations = evaluate_eligibility_rules(facts, rules)
    result = classify_eligibility(evaluations, ClaimWindowStatus.EXPIRED)
    assert result.classification is EligibilityClassification.POTENTIALLY_ELIGIBLE
    assert [reason.code for reason in result.reasons] == [
        RuleReasonCode.PURCHASE_CHANNEL_UNKNOWN,
        RuleReasonCode.PURCHASE_PRICE_UNKNOWN,
        RuleReasonCode.COUNTRY_UNKNOWN,
    ]
    assert result.rule_evaluations is evaluations
    # Supplied evaluation order is authoritative, even when it differs from PR 10.
    reversed_result = classify_eligibility(evaluations[::-1], ClaimWindowStatus.EXPIRED)
    assert reversed_result.reasons == result.reasons[::-1]


@pytest.mark.parametrize("invalid", [[], [SATISFIED], "", "rules", None, {}, {SATISFIED}])
def test_rejects_non_tuple_evaluations(invalid):
    with pytest.raises(TypeError, match="tuple"):
        classify_eligibility(invalid, ClaimWindowStatus.OPEN)


@pytest.mark.parametrize("invalid", [None, "satisfied", {}, RuleStatus.SATISFIED, 1])
def test_validates_all_tuple_members_even_after_known_failure(invalid):
    failed = replace(
        SATISFIED, status=RuleStatus.NOT_SATISFIED, reason_code=RuleReasonCode.RETAILER_MISMATCH
    )
    with pytest.raises(TypeError, match="RuleEvaluation"):
        classify_eligibility((failed, invalid), ClaimWindowStatus.OPEN)


@pytest.mark.parametrize(
    "invalid",
    [
        "open",
        "not_yet_open",
        "expired",
        1,
        *list(PromotionStatus),
        EligibilityClassification.EXPIRED,
    ],
)
def test_claim_state_requires_canonical_enum_and_rejects_promotion_lifecycle(invalid):
    with pytest.raises(TypeError, match="ClaimWindowStatus"):
        classify_eligibility((SATISFIED,), invalid)


@pytest.mark.parametrize(
    "value",
    [
        EligibilityReason(RuleReasonCode.RETAILER_MATCH, RuleKind.RETAILER),
        EligibilityReason(EligibilityReasonCode.CLAIM_WINDOW_OPEN),
        classify_eligibility((SATISFIED,), ClaimWindowStatus.OPEN),
    ],
)
def test_result_and_reasons_are_immutable(value):
    for field in fields(value):
        with pytest.raises(FrozenInstanceError):
            setattr(value, field.name, None)
    assert not hasattr(value, "__dict__")


@pytest.mark.parametrize(
    "code,kind",
    [
        ("retailer_match", RuleKind.RETAILER),
        ("customer payload", None),
        (None, None),
        (RuleReasonCode.RETAILER_MATCH, None),
        (RuleReasonCode.RETAILER_MATCH, "retailer"),
        (EligibilityReasonCode.CLAIM_WINDOW_OPEN, RuleKind.RETAILER),
    ],
)
def test_malformed_reasons_rejected(code, kind):
    with pytest.raises(TypeError):
        EligibilityReason(code, kind)


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("classification", "ELIGIBLE", TypeError),
        ("classification", PromotionStatus.EXPIRED, TypeError),
        ("reasons", [], TypeError),
        ("reasons", ("arbitrary text",), TypeError),
        ("reasons", (), ValueError),
        ("rule_evaluations", [], TypeError),
        ("rule_evaluations", (None,), TypeError),
        ("claim_window_status", "open", TypeError),
    ],
)
def test_result_construction_validates_domain_contract(field, value, error):
    result = classify_eligibility((), ClaimWindowStatus.OPEN)
    assert isinstance(result, EligibilityResult)
    with pytest.raises(error):
        replace(result, **{field: value})


@pytest.mark.parametrize("statuses", list(product(RuleStatus, repeat=3)))
def test_unspecified_window_preserves_failure_unknown_precedence(statuses):
    evaluations = tuple(
        RuleEvaluation(kind, status, codes[list(RuleStatus).index(status)])
        for status, (kind, codes) in zip(statuses, RULE_CASES, strict=True)
    )
    result = classify_eligibility(evaluations, None)
    assert result.claim_window_status is None
    assert result.rule_evaluations == evaluations
    if RuleStatus.NOT_SATISFIED in statuses:
        assert result.classification == EligibilityClassification.NOT_ELIGIBLE
        assert result.reasons == tuple(
            EligibilityReason(e.reason_code, e.kind)
            for e in evaluations
            if e.status == RuleStatus.NOT_SATISFIED
        )
    else:
        assert result.classification == EligibilityClassification.POTENTIALLY_ELIGIBLE
        assert result.reasons[-1].code == EligibilityReasonCode.CLAIM_WINDOW_UNSPECIFIED
        if RuleStatus.UNKNOWN in statuses:
            assert result.reasons[:-1] == tuple(
                EligibilityReason(e.reason_code, e.kind)
                for e in evaluations
                if e.status == RuleStatus.UNKNOWN
            )
        else:
            assert result.reasons[0].code == EligibilityReasonCode.ALL_CONFIGURED_RULES_SATISFIED
