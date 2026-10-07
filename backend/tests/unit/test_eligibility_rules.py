from dataclasses import FrozenInstanceError, fields, replace
from datetime import UTC, date, datetime
from decimal import Decimal, localcontext
from uuid import UUID

import pytest

from app.domain.eligibility_rules import (
    CountryRule,
    ManufacturerRule,
    ProductRule,
    PromotionEligibilityRules,
    PurchaseChannelRule,
    PurchaseCondition,
    PurchaseConditionRule,
    PurchaseDateRule,
    PurchaseEligibilityFacts,
    PurchasePriceRule,
    RetailerRule,
    RuleEvaluation,
    RuleKind,
    RuleReasonCode,
    RuleStatus,
    evaluate_eligibility_rules,
)
from app.domain.identity_normalisation import PurchaseChannel, resolve_purchase_channel

MAKER, PRODUCT, SHOP, OTHER = (UUID(int=i) for i in (1, 2, 3, 4))
DAY = date(2024, 2, 29)
FACTS = PurchaseEligibilityFacts(MAKER, PRODUCT, SHOP, DAY)
MEMBERSHIP_CASES = (
    (ManufacturerRule, "manufacturer_ids", "manufacturer_id", MAKER, OTHER, RuleKind.MANUFACTURER),
    (ProductRule, "product_ids", "product_id", PRODUCT, OTHER, RuleKind.PRODUCT),
    (RetailerRule, "retailer_ids", "retailer_id", SHOP, OTHER, RuleKind.RETAILER),
    (
        PurchaseChannelRule,
        "channels",
        "purchase_channel",
        PurchaseChannel.ONLINE,
        PurchaseChannel.IN_STORE,
        RuleKind.PURCHASE_CHANNEL,
    ),
    (
        PurchaseConditionRule,
        "conditions",
        "condition",
        PurchaseCondition.NEW,
        PurchaseCondition.REFURBISHED,
        RuleKind.CONDITION,
    ),
    (CountryRule, "country_codes", "country_code", "GB", "IE", RuleKind.COUNTRY),
)


def assert_result(result, kind, status, code):
    assert result == RuleEvaluation(kind, status, RuleReasonCode(code))
    assert result.reason_code == code


def test_stable_contracts():
    assert [kind.value for kind in RuleKind] == [
        "manufacturer",
        "product",
        "retailer",
        "purchase_channel",
        "purchase_date",
        "purchase_price",
        "condition",
        "country",
    ]
    assert [status.value for status in RuleStatus] == ["satisfied", "not_satisfied", "unknown"]
    assert [condition.value for condition in PurchaseCondition] == ["new", "refurbished", "used"]
    assert [field.name for field in fields(PurchaseEligibilityFacts)] == [
        "manufacturer_id",
        "product_id",
        "retailer_id",
        "purchase_date",
        "purchase_price",
        "purchase_channel",
        "condition",
        "country_code",
    ]


@pytest.mark.parametrize("field", ["manufacturer_id", "product_id", "retailer_id"])
@pytest.mark.parametrize("value", [None, "model-or-SKU", str(MAKER), 1, True, []])
def test_required_canonical_uuids(field, value):
    with pytest.raises(TypeError, match="UUID"):
        replace(FACTS, **{field: value})


@pytest.mark.parametrize("field", ["manufacturer_id", "product_id", "retailer_id", "purchase_date"])
def test_required_facts(field):
    values = {f.name: getattr(FACTS, f.name) for f in fields(FACTS) if f.name != field}
    with pytest.raises(TypeError):
        PurchaseEligibilityFacts(**values)


@pytest.mark.parametrize(
    "value", ["2024-02-29", None, 1, datetime(2024, 2, 29), datetime(2024, 2, 29, tzinfo=UTC)]
)
def test_fact_date_rejects_timestamps_and_parsing(value):
    with pytest.raises(TypeError, match="calendar date"):
        replace(FACTS, purchase_date=value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("purchase_channel", "online"),
        ("purchase_channel", "web"),
        ("purchase_channel", "shop"),
        ("purchase_channel", 1),
        ("condition", "new"),
        ("condition", "unknown"),
        ("condition", 1),
    ],
)
def test_facts_require_canonical_enums(field, value):
    with pytest.raises(TypeError):
        replace(FACTS, **{field: value})


@pytest.mark.parametrize("rule_type,field,fact_field,value,other,kind", MEMBERSHIP_CASES)
def test_membership_match_mismatch_and_multiple(rule_type, field, fact_field, value, other, kind):
    rule = rule_type(frozenset({value}))
    assert_result(
        rule.evaluate(replace(FACTS, **{fact_field: value})),
        kind,
        RuleStatus.SATISFIED,
        f"{kind.value}_match",
    )
    assert_result(
        rule.evaluate(replace(FACTS, **{fact_field: other})),
        kind,
        RuleStatus.NOT_SATISFIED,
        f"{kind.value}_mismatch",
    )
    both = rule_type(frozenset({value, other}))
    for member in (value, other):
        assert both.evaluate(replace(FACTS, **{fact_field: member})).status == RuleStatus.SATISFIED


@pytest.mark.parametrize("rule_type,field,fact_field,value,other,kind", MEMBERSHIP_CASES)
def test_empty_allowed_set_rejected(rule_type, field, fact_field, value, other, kind):
    with pytest.raises(ValueError, match="at least one"):
        rule_type(frozenset())


@pytest.mark.parametrize("rule_type,field,fact_field,value,other,kind", MEMBERSHIP_CASES)
@pytest.mark.parametrize("invalid", [None, [], "GB", 1])
def test_invalid_collection_shape(rule_type, field, fact_field, value, other, kind, invalid):
    with pytest.raises(TypeError):
        rule_type(invalid)


@pytest.mark.parametrize("rule_type,field,fact_field,value,other,kind", MEMBERSHIP_CASES)
@pytest.mark.parametrize("invalid", [None, 1, True])
def test_noncanonical_allowed_members(rule_type, field, fact_field, value, other, kind, invalid):
    with pytest.raises(TypeError):
        rule_type(frozenset({invalid}))


@pytest.mark.parametrize("rule_type,field,fact_field,value,other,kind", MEMBERSHIP_CASES)
def test_mutable_allowed_sets_copied(rule_type, field, fact_field, value, other, kind):
    values = {value}
    rule = rule_type(values)
    values.clear()
    assert getattr(rule, field) == frozenset({value})
    assert isinstance(getattr(rule, field), frozenset)


@pytest.mark.parametrize(
    "rule_type,value",
    [
        (ManufacturerRule, str(MAKER)),
        (ProductRule, "raw-model-SKU"),
        (RetailerRule, "shop"),
        (PurchaseChannelRule, "online"),
        (PurchaseChannelRule, "web"),
        (PurchaseChannelRule, "shop"),
        (PurchaseChannelRule, "website"),
        (PurchaseConditionRule, "new"),
    ],
)
def test_no_identity_or_enum_string_coercion(rule_type, value):
    with pytest.raises(TypeError):
        rule_type(frozenset({value}))


@pytest.mark.parametrize(
    "rule_type,field,value,kind",
    [
        (
            PurchaseChannelRule,
            "purchase_channel",
            PurchaseChannel.ONLINE,
            RuleKind.PURCHASE_CHANNEL,
        ),
        (PurchaseConditionRule, "condition", PurchaseCondition.NEW, RuleKind.CONDITION),
        (CountryRule, "country_code", "GB", RuleKind.COUNTRY),
    ],
)
def test_optional_missing_facts_are_unknown_without_inference(rule_type, field, value, kind):
    facts = replace(FACTS, purchase_price=Decimal("999.99"))
    assert_result(
        rule_type(frozenset({value})).evaluate(facts),
        kind,
        RuleStatus.UNKNOWN,
        f"{kind.value}_unknown",
    )


@pytest.mark.parametrize("channel", list(PurchaseChannel))
def test_each_channel_matches(channel):
    rule = PurchaseChannelRule(frozenset({channel}))
    assert rule.evaluate(replace(FACTS, purchase_channel=channel)).status == RuleStatus.SATISFIED


def test_channel_resolution_is_upstream():
    facts = replace(FACTS, purchase_channel=resolve_purchase_channel("web").channel)
    rule = PurchaseChannelRule(frozenset({PurchaseChannel.ONLINE}))
    assert rule.evaluate(facts).status == RuleStatus.SATISFIED


@pytest.mark.parametrize("condition", list(PurchaseCondition))
def test_each_condition_matches(condition):
    facts = replace(FACTS, condition=condition)
    assert (
        PurchaseConditionRule(frozenset({condition})).evaluate(facts).status == RuleStatus.SATISFIED
    )
    assert (
        PurchaseConditionRule(frozenset(PurchaseCondition)).evaluate(facts).status
        == RuleStatus.SATISFIED
    )


@pytest.mark.parametrize(
    "start,end,purchased,status,code",
    [
        (DAY, date(2024, 3, 1), DAY, RuleStatus.SATISFIED, "purchase_date_match"),
        (DAY, date(2024, 3, 1), date(2024, 3, 1), RuleStatus.SATISFIED, "purchase_date_match"),
        (
            DAY,
            date(2024, 3, 1),
            date(2024, 2, 28),
            RuleStatus.NOT_SATISFIED,
            "purchase_date_before_start",
        ),
        (
            DAY,
            date(2024, 3, 1),
            date(2024, 3, 2),
            RuleStatus.NOT_SATISFIED,
            "purchase_date_after_end",
        ),
        (DAY, DAY, DAY, RuleStatus.SATISFIED, "purchase_date_match"),
        (DAY, None, date.max, RuleStatus.SATISFIED, "purchase_date_match"),
        (DAY, None, date(2024, 2, 28), RuleStatus.NOT_SATISFIED, "purchase_date_before_start"),
        (None, DAY, date.min, RuleStatus.SATISFIED, "purchase_date_match"),
        (None, DAY, date(2024, 3, 1), RuleStatus.NOT_SATISFIED, "purchase_date_after_end"),
    ],
)
def test_inclusive_open_calendar_bounds(start, end, purchased, status, code):
    assert_result(
        PurchaseDateRule(start, end).evaluate(replace(FACTS, purchase_date=purchased)),
        RuleKind.PURCHASE_DATE,
        status,
        code,
    )


@pytest.mark.parametrize("start,end", [(None, None), (date(2024, 3, 1), DAY)])
def test_malformed_date_bounds(start, end):
    with pytest.raises(ValueError):
        PurchaseDateRule(start, end)


@pytest.mark.parametrize("field", ["start_date", "end_date"])
@pytest.mark.parametrize("value", ["2024-02-29", 1, datetime(2024, 2, 29)])
def test_date_bounds_require_calendar_date(field, value):
    with pytest.raises(TypeError):
        PurchaseDateRule(**{field: value})


@pytest.mark.parametrize(
    "minimum,maximum,price,status,code",
    [
        ("10", "20", "10", RuleStatus.SATISFIED, "purchase_price_match"),
        ("10", "20", "20", RuleStatus.SATISFIED, "purchase_price_match"),
        ("10", "20", "9.99", RuleStatus.NOT_SATISFIED, "purchase_price_below_minimum"),
        ("10", "20", "20.01", RuleStatus.NOT_SATISFIED, "purchase_price_above_maximum"),
        ("10", None, "999999999999999999.99", RuleStatus.SATISFIED, "purchase_price_match"),
        ("10", None, "0", RuleStatus.NOT_SATISFIED, "purchase_price_below_minimum"),
        (None, "20", "0", RuleStatus.SATISFIED, "purchase_price_match"),
        (None, "20", "20.01", RuleStatus.NOT_SATISFIED, "purchase_price_above_maximum"),
        ("0", "0", "0", RuleStatus.SATISFIED, "purchase_price_match"),
        ("0", "0", "-0.00", RuleStatus.SATISFIED, "purchase_price_match"),
        ("0", "0", None, RuleStatus.UNKNOWN, "purchase_price_unknown"),
    ],
)
def test_inclusive_exact_price_bounds(minimum, maximum, price, status, code):
    lower = None if minimum is None else Decimal(minimum)
    upper = None if maximum is None else Decimal(maximum)
    amount = None if price is None else Decimal(price)
    facts = replace(FACTS, purchase_price=amount)
    assert facts.purchase_price is amount
    assert_result(
        PurchasePriceRule(lower, upper).evaluate(facts), RuleKind.PURCHASE_PRICE, status, code
    )


@pytest.mark.parametrize("minimum,maximum", [(None, None), (Decimal("20"), Decimal("10"))])
def test_malformed_price_bounds(minimum, maximum):
    with pytest.raises(ValueError):
        PurchasePriceRule(minimum, maximum)


@pytest.mark.parametrize("field", ["purchase_price", "minimum", "maximum"])
@pytest.mark.parametrize("value", [0, -1, 19.99, True, "19.99"])
def test_price_types_are_not_coerced(field, value):
    with pytest.raises(TypeError):
        if field == "purchase_price":
            replace(FACTS, purchase_price=value)
        else:
            PurchasePriceRule(**{field: value})


@pytest.mark.parametrize("field", ["purchase_price", "minimum", "maximum"])
@pytest.mark.parametrize(
    "value",
    [
        Decimal("-0.01"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
        Decimal("19.999"),
        Decimal("19.990"),
        Decimal("0.000"),
    ],
)
def test_invalid_prices_never_round(field, value):
    original = value.as_tuple()
    with pytest.raises(ValueError):
        if field == "purchase_price":
            replace(FACTS, purchase_price=value)
        else:
            PurchasePriceRule(**{field: value})
    assert value.as_tuple() == original


def test_decimal_context_does_not_change_semantics():
    minimum = Decimal("123456789012345678901234567890.12")
    maximum = Decimal("123456789012345678901234567890.13")
    price = Decimal("123456789012345678901234567890.14")
    baseline = PurchasePriceRule(minimum, maximum).evaluate(replace(FACTS, purchase_price=price))
    with localcontext() as context:
        context.prec = 2
        facts = replace(FACTS, purchase_price=price)
        rule = PurchasePriceRule(minimum, maximum)
        assert facts.purchase_price is price
        assert rule.minimum is minimum and rule.maximum is maximum
        assert rule.evaluate(facts) == baseline
        assert rule.evaluate(replace(facts, purchase_price=minimum)).status == RuleStatus.SATISFIED
    assert baseline.reason_code == "purchase_price_above_maximum"


@pytest.mark.parametrize(
    "value", ["gb", "Gb", "G", "GBR", "", " GB", "G1", "G_", "ÉB", "ＧＢ", "G\n"]
)
def test_country_canonical_syntax(value):
    with pytest.raises(ValueError):
        replace(FACTS, country_code=value)
    with pytest.raises(ValueError):
        CountryRule(frozenset({value}))


@pytest.mark.parametrize("value", [1, True, [], b"GB"])
def test_country_wrong_fact_type(value):
    with pytest.raises(TypeError):
        replace(FACTS, country_code=value)


def test_country_does_not_convert_uk_to_gb():
    assert_result(
        CountryRule(frozenset({"GB"})).evaluate(replace(FACTS, country_code="UK")),
        RuleKind.COUNTRY,
        RuleStatus.NOT_SATISFIED,
        "country_mismatch",
    )


ALL_RULES = PromotionEligibilityRules(
    manufacturer=ManufacturerRule(frozenset({MAKER})),
    product=ProductRule(frozenset({OTHER})),
    retailer=RetailerRule(frozenset({OTHER})),
    purchase_channel=PurchaseChannelRule(frozenset({PurchaseChannel.ONLINE})),
    purchase_date=PurchaseDateRule(DAY, DAY),
    purchase_price=PurchasePriceRule(Decimal("0")),
    condition=PurchaseConditionRule(frozenset({PurchaseCondition.NEW})),
    country=CountryRule(frozenset({"GB"})),
)


def test_all_rules_evaluated_in_stable_order_after_failure():
    facts = replace(FACTS, country_code="IE")
    results = evaluate_eligibility_rules(facts, ALL_RULES)
    assert tuple(result.kind for result in results) == tuple(RuleKind)
    assert [result.status for result in results] == [
        RuleStatus.SATISFIED,
        RuleStatus.NOT_SATISFIED,
        RuleStatus.NOT_SATISFIED,
        RuleStatus.UNKNOWN,
        RuleStatus.SATISFIED,
        RuleStatus.UNKNOWN,
        RuleStatus.UNKNOWN,
        RuleStatus.NOT_SATISFIED,
    ]
    assert [result.reason_code for result in results] == [
        "manufacturer_match",
        "product_mismatch",
        "retailer_mismatch",
        "purchase_channel_unknown",
        "purchase_date_match",
        "purchase_price_unknown",
        "condition_unknown",
        "country_mismatch",
    ]
    for _ in range(3):
        assert evaluate_eligibility_rules(facts, ALL_RULES) == results


def test_absent_rules_have_no_results_even_with_missing_facts():
    assert evaluate_eligibility_rules(FACTS, PromotionEligibilityRules()) == ()
    rules = PromotionEligibilityRules(
        purchase_price=ALL_RULES.purchase_price,
        product=ALL_RULES.product,
        manufacturer=ALL_RULES.manufacturer,
    )
    results = evaluate_eligibility_rules(FACTS, rules)
    assert [result.kind for result in results] == [
        RuleKind.MANUFACTURER,
        RuleKind.PRODUCT,
        RuleKind.PURCHASE_PRICE,
    ]
    assert results[-1].status == RuleStatus.UNKNOWN


@pytest.mark.parametrize("field", [f.name for f in fields(PromotionEligibilityRules)])
@pytest.mark.parametrize("invalid", [False, {}, "unknown", CountryRule(frozenset({"GB"}))])
def test_malformed_aggregate_cannot_disappear(field, invalid):
    if field == "country" and isinstance(invalid, CountryRule):
        invalid = ALL_RULES.product
    with pytest.raises(TypeError):
        PromotionEligibilityRules(**{field: invalid})


@pytest.mark.parametrize(
    "value",
    [
        FACTS,
        ALL_RULES,
        *[getattr(ALL_RULES, f.name) for f in fields(ALL_RULES)],
        RuleEvaluation(RuleKind.PRODUCT, RuleStatus.SATISFIED, RuleReasonCode.PRODUCT_MATCH),
    ],
)
def test_all_values_are_immutable(value):
    for field in fields(value):
        with pytest.raises(FrozenInstanceError):
            setattr(value, field.name, None)


@pytest.mark.parametrize(
    "field,value",
    [
        ("kind", "product"),
        ("status", "eligible"),
        ("reason_code", "customer payload"),
    ],
)
def test_evaluation_contract_rejects_arbitrary_values(field, value):
    result = RuleEvaluation(RuleKind.PRODUCT, RuleStatus.SATISFIED, RuleReasonCode.PRODUCT_MATCH)
    with pytest.raises(TypeError):
        replace(result, **{field: value})


@pytest.mark.parametrize(
    "facts,rules", [(None, ALL_RULES), (FACTS, None), ({}, ALL_RULES), (FACTS, {})]
)
def test_evaluation_requires_domain_values(facts, rules):
    with pytest.raises(TypeError):
        evaluate_eligibility_rules(facts, rules)
