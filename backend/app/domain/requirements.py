"""Promotion claim requirements, independent of claimant evidence and eligibility."""

from dataclasses import dataclass
from enum import StrEnum


class RequirementType(StrEnum):
    RECEIPT = "receipt"
    SERIAL_NUMBER = "serial_number"
    REGISTRATION = "registration"
    INVOICE = "invoice"
    BARCODE = "barcode"
    IMEI = "imei"
    INSTALLATION_EVIDENCE = "installation_evidence"


@dataclass(frozen=True, slots=True)
class Requirement:
    """Claim definition; optional instructions remain passive, unparsed text."""

    requirement_type: RequirementType
    description: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "requirement_type", RequirementType(self.requirement_type))
        if self.description is not None and not isinstance(self.description, str):
            raise TypeError("Requirement description must be a string or None")
