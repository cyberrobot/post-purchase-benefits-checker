from dataclasses import FrozenInstanceError, replace
from datetime import date
from decimal import Decimal
from uuid import UUID

import pytest

from app.application.identity_matching import IdentityPersistenceError, IdentityResolver
from app.application.promotion_candidate_matching import (
    PromotionCandidate,
    PromotionCandidateSet,
    ResolvedPurchaseIdentity,
    UnresolvedPurchaseIdentity,
    match_promotion_candidates,
)
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check import CheckPurchaseRequest
from app.domain.identity_normalisation import MatchStatus
from app.domain.promotion_lifecycle import PromotionStatus

MAKER, SHOP, PRODUCT = (UUID(int=i) for i in (10, 20, 30))
REQUEST = CheckPurchaseRequest(" Maker ", " A B-1 ", " Shop ", date(2024, 2, 10))
CANDIDATE = PromotionCandidate(
    UUID(int=40), UUID(int=50), PromotionStatus.EXPIRED, None, None, None
)


class References:
    def __init__(self, calls, failure=None, candidates=()):
        self.calls = calls
        self.failure = failure
        self.candidates = candidates

    def lookup(self, stage, args, default):
        self.calls.append((stage, args))
        if self.failure == stage:
            if isinstance(self.candidates, Exception):
                raise self.candidates
            return self.candidates
        return (default,)

    def manufacturer_candidates(self, value):
        return self.lookup("brand", (value,), MAKER)

    def retailer_candidates(self, value):
        return self.lookup("retailer", (value,), SHOP)

    def model_candidates(self, value, manufacturer_id):
        return self.lookup("model", (value, manufacturer_id), PRODUCT)

    def sku_candidates(self, value, retailer_id, manufacturer_id):
        self.calls.append(("sku", (value, retailer_id, manufacturer_id)))
        return ()


class Candidates:
    def __init__(self, calls, candidates=()):
        self.calls = calls
        self.candidates = candidates

    def find_promotion_candidates(self, **kwargs):
        self.calls.append(("promotions", kwargs))
        if isinstance(self.candidates, Exception):
            raise self.candidates
        return self.candidates


def run(calls, *, failure=None, identities=(), candidates=(), request=REQUEST):
    return match_promotion_candidates(
        request,
        IdentityResolver(References(calls, failure, identities)),
        Candidates(calls, candidates),
    )


@pytest.mark.parametrize(
    "candidates",
    [(), (CANDIDATE,), (CANDIDATE, replace(CANDIDATE, promotion_variant_id=UUID(int=51)))],
)
def test_resolved_empty_one_many_and_order(candidates):
    calls = []
    result = run(calls, candidates=candidates)
    assert result == PromotionCandidateSet(
        ResolvedPurchaseIdentity(MAKER, SHOP, PRODUCT), candidates
    )
    assert calls == [
        ("brand", ("maker",)),
        ("retailer", ("shop",)),
        ("model", ("ab-1", MAKER)),
        ("sku", ("ab-1", SHOP, MAKER)),
        (
            "promotions",
            dict(
                manufacturer_id=MAKER,
                retailer_id=SHOP,
                product_id=PRODUCT,
                purchase_date=REQUEST.purchase_date,
            ),
        ),
    ]
    assert REQUEST.brand == " Maker " and REQUEST.model == " A B-1 "
    assert run([], candidates=candidates) == result


@pytest.mark.parametrize("field", ["brand", "retailer", "model"])
@pytest.mark.parametrize(
    "identities,status",
    [((), MatchStatus.NOT_FOUND), ((UUID(int=99), UUID(int=98)), MatchStatus.AMBIGUOUS)],
)
def test_unresolved_short_circuits(field, identities, status):
    calls = []
    result = run(calls, failure=field, identities=identities)
    assert result == UnresolvedPurchaseIdentity(field, status, tuple(sorted(identities)))
    assert [stage for stage, _ in calls] == {
        "brand": ["brand"],
        "retailer": ["brand", "retailer"],
        "model": ["brand", "retailer", "model", "sku"],
    }[field]


@pytest.mark.parametrize("field", ["brand", "retailer", "model"])
def test_identity_failure_propagates_without_later_reads(field):
    calls = []
    error = IdentityPersistenceError("Reference lookup failed")
    with pytest.raises(IdentityPersistenceError) as caught:
        run(calls, failure=field, identities=error)
    assert caught.value is error
    assert calls[-1][0] == field


def test_promotion_failure_is_not_empty():
    error = PromotionPersistenceError("Promotion candidate query failed")
    with pytest.raises(PromotionPersistenceError) as caught:
        run([], candidates=error)
    assert caught.value is error


@pytest.mark.parametrize("price", [None, Decimal("0"), Decimal("999.99")])
def test_price_does_not_affect_selection(price):
    calls = []
    result = run(calls, candidates=(CANDIDATE,), request=replace(REQUEST, purchase_price=price))
    baseline_calls = []
    assert result == run(baseline_calls, candidates=(CANDIDATE,))
    assert calls == baseline_calls


@pytest.mark.parametrize(
    "value,field",
    [
        (CANDIDATE, "retailer_id"),
        (ResolvedPurchaseIdentity(MAKER, SHOP, PRODUCT), "product_id"),
        (
            PromotionCandidateSet(ResolvedPurchaseIdentity(MAKER, SHOP, PRODUCT), (CANDIDATE,)),
            "candidates",
        ),
        (UnresolvedPurchaseIdentity("brand", MatchStatus.NOT_FOUND, ()), "field"),
    ],
)
def test_results_immutable(value, field):
    with pytest.raises(FrozenInstanceError):
        setattr(value, field, None)
