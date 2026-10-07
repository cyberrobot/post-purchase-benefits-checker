from dataclasses import FrozenInstanceError, fields

import pytest

from app.domain.requirements import Requirement, RequirementType


def test_stable_classifications() -> None:
    assert {member.name: member.value for member in RequirementType} == {
        "RECEIPT": "receipt",
        "SERIAL_NUMBER": "serial_number",
        "REGISTRATION": "registration",
        "INVOICE": "invoice",
        "BARCODE": "barcode",
        "IMEI": "imei",
        "INSTALLATION_EVIDENCE": "installation_evidence",
    }


@pytest.mark.parametrize("requirement_type", list(RequirementType))
def test_string_conversion(requirement_type: RequirementType) -> None:
    assert isinstance(requirement_type, str)
    assert str(requirement_type) == requirement_type.value
    assert requirement_type == requirement_type.value
    assert RequirementType(requirement_type.value) is requirement_type
    assert Requirement(requirement_type.value).requirement_type is requirement_type


@pytest.mark.parametrize("requirement_type", list(RequirementType))
@pytest.mark.parametrize("description", [None, "Human-readable instructions", ""])
def test_common_requirement(requirement_type: RequirementType, description: str | None) -> None:
    requirement = Requirement(requirement_type, description)
    assert requirement.requirement_type is requirement_type
    assert requirement.description == description
    assert requirement == Requirement(requirement_type.value, description)


@pytest.mark.parametrize(
    "value",
    ["proof", "document", "photo", "installer", "warranty_card", "other", "RECEIPT", "", None, 1],
)
def test_unsupported_classifications(value) -> None:
    with pytest.raises(ValueError):
        RequirementType(value)
    with pytest.raises(ValueError):
        Requirement(value)


def test_description_defaults_to_none() -> None:
    assert Requirement(RequirementType.SERIAL_NUMBER).description is None


@pytest.mark.parametrize("description", [1, False, [], {}, object()])
def test_description_must_be_text(description) -> None:
    with pytest.raises(TypeError, match="description must be a string or None"):
        Requirement(RequirementType.RECEIPT, description)


@pytest.mark.parametrize("field", ["requirement_type", "description"])
def test_requirement_is_immutable(field: str) -> None:
    requirement = Requirement(RequirementType.RECEIPT)
    with pytest.raises(FrozenInstanceError):
        setattr(requirement, field, "Changed")


def test_only_definition_fields_and_no_instance_dictionary() -> None:
    requirement = Requirement(RequirementType.RECEIPT)
    assert {field.name for field in fields(requirement)} == {"requirement_type", "description"}
    assert not hasattr(requirement, "__dict__")


def test_description_is_preserved_without_parsing() -> None:
    instructions = (
        "  Register within 30 days; receipt not required.\n<instruction>1 + 1</instruction>  "
    )
    requirement = Requirement(RequirementType.RECEIPT, instructions)
    assert requirement.requirement_type is RequirementType.RECEIPT
    assert requirement.description == instructions
