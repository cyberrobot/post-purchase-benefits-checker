"""Pure core purchase rules, producing rule outcomes rather than final eligibility."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.domain.identity_normalisation import PurchaseChannel
from app.domain.purchase_values import validate_purchase_date, validate_purchase_price


class RuleKind(StrEnum):
    MANUFACTURER = "manufacturer"
    PRODUCT = "product"
    RETAILER = "retailer"
    PURCHASE_CHANNEL = "purchase_channel"
    PURCHASE_DATE = "purchase_date"
    PURCHASE_PRICE = "purchase_price"
    CONDITION = "condition"
    COUNTRY = "country"


class RuleStatus(StrEnum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNKNOWN = "unknown"


class PurchaseCondition(StrEnum):
    NEW = "new"
    REFURBISHED = "refurbished"
    USED = "used"


class RuleReasonCode(StrEnum):
    MANUFACTURER_MATCH = "manufacturer_match"
    MANUFACTURER_MISMATCH = "manufacturer_mismatch"
    PRODUCT_MATCH = "product_match"
    PRODUCT_MISMATCH = "product_mismatch"
    RETAILER_MATCH = "retailer_match"
    RETAILER_MISMATCH = "retailer_mismatch"
    PURCHASE_CHANNEL_MATCH = "purchase_channel_match"
    PURCHASE_CHANNEL_MISMATCH = "purchase_channel_mismatch"
    PURCHASE_CHANNEL_UNKNOWN = "purchase_channel_unknown"
    PURCHASE_DATE_MATCH = "purchase_date_match"
    PURCHASE_DATE_BEFORE_START = "purchase_date_before_start"
    PURCHASE_DATE_AFTER_END = "purchase_date_after_end"
    PURCHASE_PRICE_MATCH = "purchase_price_match"
    PURCHASE_PRICE_BELOW_MINIMUM = "purchase_price_below_minimum"
    PURCHASE_PRICE_ABOVE_MAXIMUM = "purchase_price_above_maximum"
    PURCHASE_PRICE_UNKNOWN = "purchase_price_unknown"
    CONDITION_MATCH = "condition_match"
    CONDITION_MISMATCH = "condition_mismatch"
    CONDITION_UNKNOWN = "condition_unknown"
    COUNTRY_MATCH = "country_match"
    COUNTRY_MISMATCH = "country_mismatch"
    COUNTRY_UNKNOWN = "country_unknown"


@dataclass(frozen=True, slots=True)
class RuleEvaluation:
    kind: RuleKind
    status: RuleStatus
    reason_code: RuleReasonCode

    def __post_init__(self) -> None:
        for value, expected in (
            (self.kind, RuleKind),
            (self.status, RuleStatus),
            (self.reason_code, RuleReasonCode),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"Rule evaluation requires {expected.__name__}")


def _country(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("Country code must be a string")
    if len(value) != 2 or not all("A" <= letter <= "Z" for letter in value):
        raise ValueError("Country code must contain exactly two ASCII uppercase letters")


def _allowed[T](values: frozenset[T], expected: type[T]) -> frozenset[T]:
    # Copy mutable sets so caller mutation cannot change a configured rule.
    if not isinstance(values, (set, frozenset)):
        raise TypeError("Allowed values must be a set or frozenset")
    if not values:
        raise ValueError("A rule must allow at least one value")
    if any(not isinstance(value, expected) for value in values):
        raise TypeError(f"Allowed values must be canonical {expected.__name__} values")
    return frozenset(values)


@dataclass(frozen=True, slots=True)
class PurchaseEligibilityFacts:
    """Already-resolved identities; optional facts stay unknown until supplied."""

    manufacturer_id: UUID
    product_id: UUID
    retailer_id: UUID
    purchase_date: date
    purchase_price: Decimal | None = None
    purchase_channel: PurchaseChannel | None = None
    condition: PurchaseCondition | None = None
    country_code: str | None = None

    def __post_init__(self) -> None:
        for identity in (self.manufacturer_id, self.product_id, self.retailer_id):
            if not isinstance(identity, UUID):
                raise TypeError("Canonical identities must be UUIDs")
        validate_purchase_date(self.purchase_date)
        validate_purchase_price(self.purchase_price)
        if self.purchase_channel is not None and not isinstance(
            self.purchase_channel, PurchaseChannel
        ):
            raise TypeError("Purchase channel must be a PurchaseChannel or None")
        if self.condition is not None and not isinstance(self.condition, PurchaseCondition):
            raise TypeError("Condition must be a PurchaseCondition or None")
        if self.country_code is not None:
            _country(self.country_code)


def _membership[T](kind: RuleKind, value: T | None, allowed: frozenset[T]) -> RuleEvaluation:
    if value is None:
        status, suffix = RuleStatus.UNKNOWN, "unknown"
    elif value in allowed:
        status, suffix = RuleStatus.SATISFIED, "match"
    else:
        status, suffix = RuleStatus.NOT_SATISFIED, "mismatch"
    return RuleEvaluation(kind, status, RuleReasonCode(f"{kind.value}_{suffix}"))


@dataclass(frozen=True, slots=True)
class ManufacturerRule:
    manufacturer_ids: frozenset[UUID]

    def __post_init__(self) -> None:
        object.__setattr__(self, "manufacturer_ids", _allowed(self.manufacturer_ids, UUID))

    def evaluate(self, facts: PurchaseEligibilityFacts) -> RuleEvaluation:
        return _membership(RuleKind.MANUFACTURER, facts.manufacturer_id, self.manufacturer_ids)


@dataclass(frozen=True, slots=True)
class ProductRule:
    """Model and retailer SKU applicability use only their resolved Product.id."""

    product_ids: frozenset[UUID]

    def __post_init__(self) -> None:
        object.__setattr__(self, "product_ids", _allowed(self.product_ids, UUID))

    def evaluate(self, facts: PurchaseEligibilityFacts) -> RuleEvaluation:
        return _membership(RuleKind.PRODUCT, facts.product_id, self.product_ids)


@dataclass(frozen=True, slots=True)
class RetailerRule:
    retailer_ids: frozenset[UUID]

    def __post_init__(self) -> None:
        object.__setattr__(self, "retailer_ids", _allowed(self.retailer_ids, UUID))

    def evaluate(self, facts: PurchaseEligibilityFacts) -> RuleEvaluation:
        return _membership(RuleKind.RETAILER, facts.retailer_id, self.retailer_ids)


@dataclass(frozen=True, slots=True)
class PurchaseChannelRule:
    channels: frozenset[PurchaseChannel]

    def __post_init__(self) -> None:
        object.__setattr__(self, "channels", _allowed(self.channels, PurchaseChannel))

    def evaluate(self, facts: PurchaseEligibilityFacts) -> RuleEvaluation:
        return _membership(RuleKind.PURCHASE_CHANNEL, facts.purchase_channel, self.channels)


@dataclass(frozen=True, slots=True)
class PurchaseDateRule:
    start_date: date | None = None
    end_date: date | None = None

    def __post_init__(self) -> None:
        if self.start_date is None and self.end_date is None:
            raise ValueError("A purchase date rule requires at least one bound")
        for bound in (self.start_date, self.end_date):
            if bound is not None:
                validate_purchase_date(bound)
        if self.start_date is not None and self.end_date is not None:
            if self.start_date > self.end_date:
                raise ValueError("Purchase start date must not follow end date")

    def evaluate(self, facts: PurchaseEligibilityFacts) -> RuleEvaluation:
        if self.start_date is not None and facts.purchase_date < self.start_date:
            return RuleEvaluation(
                RuleKind.PURCHASE_DATE,
                RuleStatus.NOT_SATISFIED,
                RuleReasonCode.PURCHASE_DATE_BEFORE_START,
            )
        if self.end_date is not None and facts.purchase_date > self.end_date:
            return RuleEvaluation(
                RuleKind.PURCHASE_DATE,
                RuleStatus.NOT_SATISFIED,
                RuleReasonCode.PURCHASE_DATE_AFTER_END,
            )
        return RuleEvaluation(
            RuleKind.PURCHASE_DATE, RuleStatus.SATISFIED, RuleReasonCode.PURCHASE_DATE_MATCH
        )


@dataclass(frozen=True, slots=True)
class PurchasePriceRule:
    """Inclusive exact GBP bounds, independent of Decimal context precision."""

    minimum: Decimal | None = None
    maximum: Decimal | None = None

    def __post_init__(self) -> None:
        if self.minimum is None and self.maximum is None:
            raise ValueError("A purchase price rule requires at least one bound")
        validate_purchase_price(self.minimum)
        validate_purchase_price(self.maximum)
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError("Minimum purchase price must not exceed maximum")

    def evaluate(self, facts: PurchaseEligibilityFacts) -> RuleEvaluation:
        price = facts.purchase_price
        if price is None:
            return RuleEvaluation(
                RuleKind.PURCHASE_PRICE, RuleStatus.UNKNOWN, RuleReasonCode.PURCHASE_PRICE_UNKNOWN
            )
        if self.minimum is not None and price < self.minimum:
            return RuleEvaluation(
                RuleKind.PURCHASE_PRICE,
                RuleStatus.NOT_SATISFIED,
                RuleReasonCode.PURCHASE_PRICE_BELOW_MINIMUM,
            )
        if self.maximum is not None and price > self.maximum:
            return RuleEvaluation(
                RuleKind.PURCHASE_PRICE,
                RuleStatus.NOT_SATISFIED,
                RuleReasonCode.PURCHASE_PRICE_ABOVE_MAXIMUM,
            )
        return RuleEvaluation(
            RuleKind.PURCHASE_PRICE, RuleStatus.SATISFIED, RuleReasonCode.PURCHASE_PRICE_MATCH
        )


@dataclass(frozen=True, slots=True)
class PurchaseConditionRule:
    conditions: frozenset[PurchaseCondition]

    def __post_init__(self) -> None:
        object.__setattr__(self, "conditions", _allowed(self.conditions, PurchaseCondition))

    def evaluate(self, facts: PurchaseEligibilityFacts) -> RuleEvaluation:
        return _membership(RuleKind.CONDITION, facts.condition, self.conditions)


@dataclass(frozen=True, slots=True)
class CountryRule:
    country_codes: frozenset[str]

    def __post_init__(self) -> None:
        codes = _allowed(self.country_codes, str)
        for code in codes:
            _country(code)
        object.__setattr__(self, "country_codes", codes)

    def evaluate(self, facts: PurchaseEligibilityFacts) -> RuleEvaluation:
        return _membership(RuleKind.COUNTRY, facts.country_code, self.country_codes)


@dataclass(frozen=True, slots=True)
class PromotionEligibilityRules:
    """Absent rules impose no restriction; malformed configured rules are rejected."""

    manufacturer: ManufacturerRule | None = None
    product: ProductRule | None = None
    retailer: RetailerRule | None = None
    purchase_channel: PurchaseChannelRule | None = None
    purchase_date: PurchaseDateRule | None = None
    purchase_price: PurchasePriceRule | None = None
    condition: PurchaseConditionRule | None = None
    country: CountryRule | None = None

    def __post_init__(self) -> None:
        for rule, expected in (
            (self.manufacturer, ManufacturerRule),
            (self.product, ProductRule),
            (self.retailer, RetailerRule),
            (self.purchase_channel, PurchaseChannelRule),
            (self.purchase_date, PurchaseDateRule),
            (self.purchase_price, PurchasePriceRule),
            (self.condition, PurchaseConditionRule),
            (self.country, CountryRule),
        ):
            if rule is not None and not isinstance(rule, expected):
                raise TypeError(f"Configured rule must be a {expected.__name__} or None")


def evaluate_eligibility_rules(
    facts: PurchaseEligibilityFacts, rules: PromotionEligibilityRules
) -> tuple[RuleEvaluation, ...]:
    """Evaluate all configured dimensions in stable order, without classification."""
    if not isinstance(facts, PurchaseEligibilityFacts):
        raise TypeError("Facts must be PurchaseEligibilityFacts")
    if not isinstance(rules, PromotionEligibilityRules):
        raise TypeError("Rules must be PromotionEligibilityRules")
    return tuple(
        rule.evaluate(facts)
        for rule in (
            rules.manufacturer,
            rules.product,
            rules.retailer,
            rules.purchase_channel,
            rules.purchase_date,
            rules.purchase_price,
            rules.condition,
            rules.country,
        )
        if rule is not None
    )
