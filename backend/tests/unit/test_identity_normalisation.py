from dataclasses import FrozenInstanceError
from uuid import UUID

import pytest

from app.domain.identity_normalisation import (
    ChannelMatchResult,
    MatchResult,
    MatchStatus,
    PurchaseChannel,
    normalise_identifier,
    normalise_text,
    resolve_purchase_channel,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("  Example   Retailer \t", "example retailer"),
        ("EXAMPLE RETAILER", "example retailer"),
        ("Ｅｘａｍｐｌｅ\u00a0Retailer", "example retailer"),
        ("Straße", "strasse"),
        ("a\n\t b", "a b"),
        ("A+B", "a+b"),
        ("A-B", "a-b"),
        ("AB", "ab"),
    ],
)
def test_human_text(raw, expected):
    assert normalise_text(raw) == expected
    assert normalise_text(normalise_text(raw)) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        (" QE55 S95D ", "qe55s95d"),
        ("AB-123", "ab-123"),
        ("AB123", "ab123"),
        ("ＡＢ\t１２３", "ab123"),
        ("Straße\u00a0\n1", "strasse1"),
    ],
)
def test_identifiers(raw, expected):
    assert normalise_identifier(raw) == expected
    assert normalise_identifier(normalise_identifier(raw)) == expected


@pytest.mark.parametrize("normaliser", [normalise_text, normalise_identifier])
@pytest.mark.parametrize(
    "value", ["", " \t\n\u00a0", "a" * 256, "ß" * 255, "bad\0input", "bad\x7finput"]
)
def test_invalid_or_oversized_input(normaliser, value):
    with pytest.raises(ValueError):
        normaliser(value)


@pytest.mark.parametrize("normaliser", [normalise_text, normalise_identifier])
@pytest.mark.parametrize("value", [None, 123, [], b"text"])
def test_non_string_input(normaliser, value):
    with pytest.raises(TypeError):
        normaliser(value)


@pytest.mark.parametrize("normaliser", [normalise_text, normalise_identifier])
def test_exact_length_boundary_and_punctuation(normaliser):
    assert normaliser("a" * 255) == "a" * 255
    assert len({normaliser(v) for v in ("A+B", "AB", "A-B")}) == 3


@pytest.mark.parametrize(
    "candidates,status,canonical",
    [
        ((), MatchStatus.NOT_FOUND, None),
        ((UUID(int=1),), MatchStatus.MATCHED, UUID(int=1)),
        ((UUID(int=1), UUID(int=1)), MatchStatus.MATCHED, UUID(int=1)),
        ((UUID(int=2), UUID(int=1), UUID(int=2)), MatchStatus.AMBIGUOUS, None),
    ],
)
def test_match_invariants(candidates, status, canonical):
    result = MatchResult.from_candidates(iter(candidates))
    assert result.status == status
    assert result.canonical_id == canonical
    assert result.candidate_ids == tuple(sorted(set(candidates)))
    assert MatchResult(tuple(reversed(candidates))) == result
    with pytest.raises(FrozenInstanceError):
        result.candidate_ids = ()


def test_match_rejects_noncanonical_id():
    with pytest.raises(TypeError):
        MatchResult(("some-id",))


def test_stable_enum_values():
    assert [s.value for s in MatchStatus] == ["matched", "not_found", "ambiguous"]
    assert [s.value for s in PurchaseChannel] == ["online", "in_store"]


@pytest.mark.parametrize("value", ["online", "web", "website", " ＷＥＢ "])
def test_online(value):
    result = resolve_purchase_channel(value)
    assert result == ChannelMatchResult(PurchaseChannel.ONLINE)
    assert result.status == MatchStatus.MATCHED


@pytest.mark.parametrize("value", ["in_store", "in-store", "instore", "store", "shop", " SHOP "])
def test_in_store(value):
    result = resolve_purchase_channel(value)
    assert result.channel == PurchaseChannel.IN_STORE
    assert result.status == MatchStatus.MATCHED


@pytest.mark.parametrize(
    "value", ["other", "mobile", "marketplace", "in store", "shop!", "delivery"]
)
def test_unsupported_channels(value):
    result = resolve_purchase_channel(value)
    assert result.channel is None
    assert result.status == MatchStatus.NOT_FOUND


@pytest.mark.parametrize("value", ["", " \t", "x" * 256])
def test_invalid_channels(value):
    with pytest.raises(ValueError):
        resolve_purchase_channel(value)


def test_channel_result_validates_and_is_immutable():
    with pytest.raises(ValueError):
        ChannelMatchResult("other")
    with pytest.raises(FrozenInstanceError):
        ChannelMatchResult(PurchaseChannel.ONLINE).channel = None
