"""Read-only canonical identity resolution over an application-owned reference port."""

from typing import Protocol
from uuid import UUID

from app.domain.identity_normalisation import MatchResult, normalise_identifier, normalise_text


class IdentityPersistenceError(RuntimeError):
    """Safe infrastructure failure; never a not-found/ambiguous match outcome."""


class IdentityRepository(Protocol):
    def manufacturer_candidates(self, normalised: str) -> tuple[UUID, ...]: ...
    def retailer_candidates(self, normalised: str) -> tuple[UUID, ...]: ...
    def retailer_group_candidates(self, normalised: str) -> tuple[UUID, ...]: ...
    def model_candidates(self, normalised: str, manufacturer_id: UUID) -> tuple[UUID, ...]: ...
    def sku_candidates(
        self, normalised: str, retailer_id: UUID, manufacturer_id: UUID | None
    ) -> tuple[UUID, ...]: ...
    def retailer_group_ids(self, retailer_id: UUID) -> tuple[UUID, ...]: ...


def _identity(value: UUID) -> UUID:
    if not isinstance(value, UUID):
        raise TypeError("Canonical context must be a UUID")
    return value


class IdentityResolver:
    def __init__(self, repository: IdentityRepository):
        self.repository = repository

    def resolve_manufacturer(self, value: str) -> MatchResult:
        return MatchResult(self.repository.manufacturer_candidates(normalise_text(value)))

    def resolve_retailer(self, value: str) -> MatchResult:
        return MatchResult(self.repository.retailer_candidates(normalise_text(value)))

    def resolve_retailer_group(self, value: str) -> MatchResult:
        return MatchResult(self.repository.retailer_group_candidates(normalise_text(value)))

    def resolve_model(self, value: str, *, manufacturer_id: UUID) -> MatchResult:
        normalised = normalise_identifier(value)
        return MatchResult(self.repository.model_candidates(normalised, _identity(manufacturer_id)))

    def resolve_sku(
        self, value: str, *, retailer_id: UUID, manufacturer_id: UUID | None = None
    ) -> MatchResult:
        normalised = normalise_identifier(value)
        retailer_id = _identity(retailer_id)
        if manufacturer_id is not None:
            manufacturer_id = _identity(manufacturer_id)
        return MatchResult(self.repository.sku_candidates(normalised, retailer_id, manufacturer_id))

    def resolve_product(
        self,
        value: str,
        *,
        manufacturer_id: UUID | None = None,
        retailer_id: UUID | None = None,
    ) -> MatchResult:
        """Resolve one model-or-SKU field; union exact candidates without preference."""
        normalised = normalise_identifier(value)
        if manufacturer_id is None and retailer_id is None:
            raise ValueError("Product matching requires manufacturer or retailer context")
        if manufacturer_id is not None:
            manufacturer_id = _identity(manufacturer_id)
        if retailer_id is not None:
            retailer_id = _identity(retailer_id)
        candidates = []
        if manufacturer_id is not None:
            candidates.extend(self.repository.model_candidates(normalised, manufacturer_id))
        if retailer_id is not None:
            candidates.extend(
                self.repository.sku_candidates(normalised, retailer_id, manufacturer_id)
            )
        return MatchResult.from_candidates(candidates)

    def retailer_group_ids(self, retailer_id: UUID) -> tuple[UUID, ...]:
        """Current memberships only; no historical or promotion applicability inference."""
        return tuple(sorted(set(self.repository.retailer_group_ids(_identity(retailer_id)))))
