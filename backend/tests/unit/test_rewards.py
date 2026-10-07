from dataclasses import FrozenInstanceError, fields
from decimal import ROUND_DOWN, ROUND_UP, Decimal, Inexact, Rounded, localcontext
from uuid import UUID, uuid4

import pytest

from app.domain.benefits import Benefit, BenefitType
from app.domain.rewards import (
    FixedAmountReward,
    MissingProductReward,
    MissingPurchasePrice,
    PercentageReward,
    ProductRewardValue,
    ProductSpecificReward,
    RewardType,
    calculate_reward,
)


def test_discriminators() -> None:
    assert {member.name: member.value for member in RewardType} == {
        "FIXED_AMOUNT": "fixed_amount",
        "PERCENTAGE": "percentage",
        "PRODUCT_SPECIFIC": "product_specific",
    }
    for member in RewardType:
        assert isinstance(member, str)
        assert str(member) == member.value
        assert RewardType(member.value) is member


@pytest.mark.parametrize("value", ["FIXED_AMOUNT", "basket", "conditional", "other", "", None])
def test_unknown_discriminators(value) -> None:
    with pytest.raises(ValueError):
        RewardType(value)


@pytest.mark.parametrize("amount", [Decimal("100"), Decimal("100.00"), Decimal("0.01")])
def test_fixed_amount_is_exact_and_independent_of_other_inputs(amount: Decimal) -> None:
    reward = FixedAmountReward(amount)
    assert reward.reward_type is RewardType.FIXED_AMOUNT
    assert calculate_reward(reward) is amount
    assert calculate_reward(reward, purchase_price=Decimal("0"), product_id=uuid4()) is amount


@pytest.mark.parametrize(
    "constructor", [FixedAmountReward, lambda v: ProductRewardValue(uuid4(), v)]
)
@pytest.mark.parametrize(
    "value", ["NaN", "sNaN", "Infinity", "-Infinity", "0", "-1", "12.345", "1.000"]
)
def test_invalid_amounts(constructor, value: str) -> None:
    with pytest.raises(ValueError):
        constructor(Decimal(value))


@pytest.mark.parametrize(
    "constructor",
    [FixedAmountReward, PercentageReward, lambda v: ProductRewardValue(uuid4(), v)],
)
@pytest.mark.parametrize("value", [1.2, 1, "12.00", None, True])
def test_numeric_types_are_not_coerced(constructor, value) -> None:
    with pytest.raises(TypeError):
        constructor(value)


@pytest.mark.parametrize(
    "value", ["NaN", "sNaN", "Infinity", "-Infinity", "0", "-1", "100.0001", "0.00001"]
)
def test_invalid_percentage(value: str) -> None:
    with pytest.raises(ValueError):
        PercentageReward(Decimal(value))


@pytest.mark.parametrize(
    "price,percentage,expected",
    [
        ("199.99", "10", "20.00"),
        ("100.00", "12.5", "12.50"),
        ("0.10", "5", "0.01"),
        ("0.09", "5", "0.00"),
        ("0.11", "5", "0.01"),
        ("0.00", "10", "0.00"),
        ("123.45", "100", "123.45"),
        ("10000", "0.0001", "0.01"),
        (
            "999999999999999999999999999999999999.99",
            "100",
            "999999999999999999999999999999999999.99",
        ),
        ("1E+50", "10", "1" + "0" * 49 + ".00"),
    ],
)
def test_percentage_calculation(price: str, percentage: str, expected: str) -> None:
    reward = PercentageReward(Decimal(percentage))
    assert reward.reward_type is RewardType.PERCENTAGE
    result = calculate_reward(reward, purchase_price=Decimal(price))
    assert result == Decimal(expected)
    assert result.as_tuple().exponent == -2


@pytest.mark.parametrize("rounding", [ROUND_DOWN, ROUND_UP])
def test_percentage_ignores_ambient_context(rounding: str) -> None:
    reward = PercentageReward(Decimal("12.3456"))
    price = Decimal("12345678901234567890.15")
    expected = calculate_reward(reward, purchase_price=price)
    with localcontext() as context:
        context.prec = 2
        context.rounding = rounding
        context.Emax = 2
        context.Emin = -2
        context.traps[Inexact] = True
        context.traps[Rounded] = True
        assert calculate_reward(reward, purchase_price=price) == expected
        assert context.prec == 2
        assert not context.flags[Inexact]
        assert not context.flags[Rounded]


def test_missing_purchase_price() -> None:
    with pytest.raises(MissingPurchasePrice):
        calculate_reward(PercentageReward(Decimal("10")))


@pytest.mark.parametrize("value", [1, 1.1, "1", True])
def test_invalid_purchase_price_type(value) -> None:
    with pytest.raises(TypeError, match="Purchase price"):
        calculate_reward(PercentageReward(Decimal("10")), purchase_price=value)


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "0.001", "1.000"])
def test_invalid_purchase_price_value(value: str) -> None:
    with pytest.raises(ValueError, match="Purchase price"):
        calculate_reward(PercentageReward(Decimal("10")), purchase_price=Decimal(value))


def test_product_values_are_canonical_frozen_and_order_independent() -> None:
    a = ProductRewardValue(UUID(int=1), Decimal("100.00"))
    b = ProductRewardValue(UUID(int=2), Decimal("150.00"))
    supplied = [b, a]
    reward = ProductSpecificReward(supplied)
    supplied.clear()
    assert reward.reward_type is RewardType.PRODUCT_SPECIFIC
    assert reward == ProductSpecificReward((a, b))
    assert hash(reward) == hash(ProductSpecificReward((b, a)))
    assert reward.values == (a, b)
    assert calculate_reward(reward, product_id=a.product_id) is a.amount
    assert calculate_reward(reward, product_id=b.product_id) is b.amount
    with pytest.raises(MissingProductReward):
        calculate_reward(reward, product_id=UUID(int=3))


@pytest.mark.parametrize("value", ["model-1", "00000000-0000-0000-0000-000000000001", 1, None])
def test_product_uuid_validation(value) -> None:
    with pytest.raises(TypeError):
        ProductRewardValue(value, Decimal("1"))
    reward = ProductSpecificReward((ProductRewardValue(UUID(int=1), Decimal("1")),))
    with pytest.raises(TypeError):
        calculate_reward(reward, product_id=value)


def test_product_configuration_validation() -> None:
    a = ProductRewardValue(uuid4(), Decimal("1"))
    for values in ([], (), (a, a)):
        with pytest.raises(ValueError):
            ProductSpecificReward(values)
    for values in (None, {}, ("untyped",)):
        with pytest.raises(TypeError):
            ProductSpecificReward(values)


@pytest.mark.parametrize(
    "value",
    [
        FixedAmountReward(Decimal("1")),
        PercentageReward(Decimal("1")),
        ProductRewardValue(UUID(int=1), Decimal("1")),
        ProductSpecificReward((ProductRewardValue(UUID(int=1), Decimal("1")),)),
    ],
)
def test_values_are_frozen_and_slotted(value) -> None:
    assert not hasattr(value, "__dict__")
    with pytest.raises(FrozenInstanceError):
        setattr(value, fields(value)[0].name, None)


def test_display_text_is_not_a_reward_definition() -> None:
    benefit = Benefit(BenefitType.CASHBACK, "£999 cashback", "50% reward")
    assert {field.name for field in fields(benefit)} == {"benefit_type", "name", "description"}
    with pytest.raises(TypeError):
        calculate_reward(benefit)
    for value in ("fixed_amount", {"amount": Decimal("999")}, None):
        with pytest.raises(TypeError):
            calculate_reward(value)
