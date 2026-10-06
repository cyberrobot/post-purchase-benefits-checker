from unittest.mock import Mock
from uuid import UUID

import pytest

from app.application.identity_matching import (
    IdentityPersistenceError,
    IdentityRepository,
    IdentityResolver,
)
from app.domain.identity_normalisation import MatchStatus

MANUFACTURER = UUID(int=10)
RETAILER = UUID(int=20)
PRODUCT = UUID(int=30)


@pytest.fixture
def repository():
    return Mock(spec=IdentityRepository)


@pytest.mark.parametrize(
    "operation,port",
    [
        ("resolve_manufacturer", "manufacturer_candidates"),
        ("resolve_retailer", "retailer_candidates"),
        ("resolve_retailer_group", "retailer_group_candidates"),
    ],
)
def test_named_resolution(repository, operation, port):
    getattr(repository, port).return_value = (PRODUCT,)
    result = getattr(IdentityResolver(repository), operation)(" ＥＸＡＭＰＬＥ   Name ")
    assert result.canonical_id == PRODUCT
    getattr(repository, port).assert_called_once_with("example name")


@pytest.mark.parametrize("value", ["", " \t", "a" * 256, None, 1])
@pytest.mark.parametrize(
    "operation,kwargs",
    [
        ("resolve_manufacturer", {}),
        ("resolve_retailer", {}),
        ("resolve_retailer_group", {}),
        ("resolve_model", {"manufacturer_id": MANUFACTURER}),
        ("resolve_sku", {"retailer_id": RETAILER}),
        ("resolve_product", {"manufacturer_id": MANUFACTURER, "retailer_id": RETAILER}),
    ],
)
def test_invalid_input_does_not_read(repository, value, operation, kwargs):
    with pytest.raises((ValueError, TypeError)):
        getattr(IdentityResolver(repository), operation)(value, **kwargs)
    assert repository.mock_calls == []


@pytest.mark.parametrize(
    "model,sku,expected",
    [
        ((), (), MatchStatus.NOT_FOUND),
        ((PRODUCT,), (), MatchStatus.MATCHED),
        ((), (PRODUCT,), MatchStatus.MATCHED),
        ((PRODUCT,), (PRODUCT,), MatchStatus.MATCHED),
        ((PRODUCT,), (UUID(int=31),), MatchStatus.AMBIGUOUS),
        ((PRODUCT, UUID(int=31)), (PRODUCT,), MatchStatus.AMBIGUOUS),
    ],
)
def test_combined_candidates(repository, model, sku, expected):
    repository.model_candidates.return_value = model
    repository.sku_candidates.return_value = sku
    result = IdentityResolver(repository).resolve_product(
        " A B-1 ", manufacturer_id=MANUFACTURER, retailer_id=RETAILER
    )
    assert result.status == expected
    assert result.candidate_ids == tuple(sorted(set(model + sku)))
    repository.model_candidates.assert_called_once_with("ab-1", MANUFACTURER)
    repository.sku_candidates.assert_called_once_with("ab-1", RETAILER, MANUFACTURER)


@pytest.mark.parametrize("scope", ["manufacturer", "retailer"])
def test_single_context(repository, scope):
    repository.model_candidates.return_value = (PRODUCT,)
    repository.sku_candidates.return_value = (PRODUCT,)
    kwargs = (
        {"manufacturer_id": MANUFACTURER} if scope == "manufacturer" else {"retailer_id": RETAILER}
    )
    assert IdentityResolver(repository).resolve_product("AB1", **kwargs).canonical_id == PRODUCT
    if scope == "manufacturer":
        repository.sku_candidates.assert_not_called()
    else:
        repository.model_candidates.assert_not_called()
        repository.sku_candidates.assert_called_once_with("ab1", RETAILER, None)


def test_requires_context_before_reading(repository):
    with pytest.raises(ValueError):
        IdentityResolver(repository).resolve_product("AB1")
    assert repository.mock_calls == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"manufacturer_id": "bad"},
        {"retailer_id": "bad"},
        {"manufacturer_id": MANUFACTURER, "retailer_id": "bad"},
    ],
)
def test_invalid_context_before_any_read(repository, kwargs):
    with pytest.raises(TypeError):
        IdentityResolver(repository).resolve_product("AB1", **kwargs)
    assert repository.mock_calls == []


def test_separate_identifier_operations(repository):
    repository.model_candidates.return_value = (PRODUCT,)
    repository.sku_candidates.return_value = (PRODUCT,)
    resolver = IdentityResolver(repository)
    assert resolver.resolve_model(" A B1 ", manufacturer_id=MANUFACTURER).canonical_id == PRODUCT
    assert resolver.resolve_sku(" A B1 ", retailer_id=RETAILER).canonical_id == PRODUCT
    repository.model_candidates.assert_called_once_with("ab1", MANUFACTURER)
    repository.sku_candidates.assert_called_once_with("ab1", RETAILER, None)


def test_memberships_sorted_without_applicability(repository):
    repository.retailer_group_ids.return_value = (UUID(int=2), UUID(int=1), UUID(int=2))
    assert IdentityResolver(repository).retailer_group_ids(RETAILER) == (UUID(int=1), UUID(int=2))
    repository.retailer_group_ids.assert_called_once_with(RETAILER)


@pytest.mark.parametrize(
    "operation,port,kwargs",
    [
        ("resolve_manufacturer", "manufacturer_candidates", {}),
        ("resolve_retailer", "retailer_candidates", {}),
        ("resolve_retailer_group", "retailer_group_candidates", {}),
        ("resolve_model", "model_candidates", {"manufacturer_id": MANUFACTURER}),
        ("resolve_sku", "sku_candidates", {"retailer_id": RETAILER}),
        ("resolve_product", "sku_candidates", {"retailer_id": RETAILER}),
    ],
)
def test_infrastructure_failures_are_not_matches(repository, operation, port, kwargs):
    getattr(repository, port).side_effect = IdentityPersistenceError("Lookup failed")
    with pytest.raises(IdentityPersistenceError):
        getattr(IdentityResolver(repository), operation)("AB1", **kwargs)
