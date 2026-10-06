from dataclasses import FrozenInstanceError

import pytest

from app.domain.benefits import Benefit, BenefitType


def test_stable_classifications() -> None:
    assert {member.name: member.value for member in BenefitType} == {
        "CASHBACK": "cashback",
        "EXTENDED_WARRANTY": "extended_warranty",
        "FREE_GIFT": "free_gift",
    }


@pytest.mark.parametrize("benefit_type", list(BenefitType))
def test_string_conversion(benefit_type: BenefitType) -> None:
    assert isinstance(benefit_type, str)
    assert str(benefit_type) == benefit_type.value
    assert benefit_type == benefit_type.value
    assert BenefitType(benefit_type.value) is benefit_type
    assert Benefit(benefit_type.value, "Display text").benefit_type is benefit_type


@pytest.mark.parametrize("value", ["rebate", "gift", "warranty", "CASHBACK", "other", ""])
def test_unsupported_classifications(value: str) -> None:
    with pytest.raises(ValueError):
        BenefitType(value)
    with pytest.raises(ValueError):
        Benefit(value, "Display text")


@pytest.mark.parametrize(
    "benefit_type,name",
    [
        (BenefitType.CASHBACK, "£100 cashback"),
        (BenefitType.EXTENDED_WARRANTY, "5 year warranty"),
        (BenefitType.FREE_GIFT, "Free headphones"),
    ],
)
@pytest.mark.parametrize("description", [None, "Human-readable terms", ""])
def test_common_benefit(benefit_type: BenefitType, name: str, description: str | None) -> None:
    benefit = Benefit(benefit_type, name, description)
    assert benefit.benefit_type is benefit_type
    assert benefit.name == name
    assert benefit.description == description


def test_description_defaults_to_none() -> None:
    assert Benefit(BenefitType.CASHBACK, "Cashback").description is None


@pytest.mark.parametrize("field", ["benefit_type", "name", "description"])
def test_benefit_is_immutable(field: str) -> None:
    benefit = Benefit(BenefitType.CASHBACK, "Cashback")
    with pytest.raises(FrozenInstanceError):
        setattr(benefit, field, "Changed")


@pytest.mark.parametrize("name,description", [(None, None), (100, None), ("Gift", 100)])
def test_display_text_must_be_text(name, description) -> None:
    with pytest.raises(TypeError):
        Benefit(BenefitType.FREE_GIFT, name, description)
