"""Broad published promotion matching, before any detailed eligibility evaluation."""

from dataclasses import dataclass
from datetime import date
from typing import Literal, Protocol
from uuid import UUID

from app.application.identity_matching import IdentityResolver
from app.application.purchase_check import CheckPurchaseRequest
from app.domain.identity_normalisation import MatchStatus
from app.domain.promotion_lifecycle import PromotionStatus


@dataclass(frozen=True, slots=True)
class ResolvedPurchaseIdentity:
    manufacturer_id: UUID
    retailer_id: UUID
    product_id: UUID


@dataclass(frozen=True, slots=True)
class UnresolvedPurchaseIdentity:
    field: Literal["brand", "retailer", "model"]
    status: MatchStatus
    candidate_ids: tuple[UUID, ...]

    @property
    def explanation(self) -> str:
        from app.application.purchase_check import explain_unresolved_identity

        return explain_unresolved_identity(self)


@dataclass(frozen=True, slots=True)
class PromotionCandidate:
    promotion_id: UUID
    promotion_variant_id: UUID
    promotion_status: PromotionStatus
    retailer_id: UUID | None
    purchase_start_date: date | None
    purchase_end_date: date | None


@dataclass(frozen=True, slots=True)
class PromotionCandidateSet:
    identity: ResolvedPurchaseIdentity
    candidates: tuple[PromotionCandidate, ...]


class PromotionCandidateRepository(Protocol):
    def find_promotion_candidates(
        self,
        *,
        manufacturer_id: UUID,
        product_id: UUID,
        retailer_id: UUID,
        purchase_date: date,
    ) -> tuple[PromotionCandidate, ...]: ...


def match_promotion_candidates(
    request: CheckPurchaseRequest,
    identity_resolver: IdentityResolver,
    repository: PromotionCandidateRepository,
) -> PromotionCandidateSet | UnresolvedPurchaseIdentity:
    """Resolve exact identities in order; uncertainty and infrastructure failure stay distinct."""
    manufacturer = identity_resolver.resolve_manufacturer(request.brand)
    if manufacturer.status != MatchStatus.MATCHED:
        return UnresolvedPurchaseIdentity("brand", manufacturer.status, manufacturer.candidate_ids)
    retailer = identity_resolver.resolve_retailer(request.retailer)
    if retailer.status != MatchStatus.MATCHED:
        return UnresolvedPurchaseIdentity("retailer", retailer.status, retailer.candidate_ids)
    manufacturer_id = manufacturer.canonical_id
    retailer_id = retailer.canonical_id
    assert manufacturer_id is not None and retailer_id is not None
    product = identity_resolver.resolve_product(
        request.model, manufacturer_id=manufacturer_id, retailer_id=retailer_id
    )
    if product.status != MatchStatus.MATCHED:
        return UnresolvedPurchaseIdentity("model", product.status, product.candidate_ids)
    product_id = product.canonical_id
    assert product_id is not None
    identity = ResolvedPurchaseIdentity(manufacturer_id, retailer_id, product_id)
    candidates = repository.find_promotion_candidates(
        manufacturer_id=manufacturer_id,
        product_id=product_id,
        retailer_id=retailer_id,
        purchase_date=request.purchase_date,
    )
    return PromotionCandidateSet(identity, candidates)
