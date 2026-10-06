"""Conservative, deterministic reference identity matching; no eligibility rules."""

import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

MAX_IDENTITY_LENGTH = 255


def _bounded(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Identity input must be a string")
    if not value or len(value) > MAX_IDENTITY_LENGTH:
        raise ValueError("Identity input must contain 1 to 255 characters")
    if any(unicodedata.category(c) == "Cc" and not c.isspace() for c in value):
        raise ValueError("Identity input contains unsupported control characters")
    return value


def normalise_text(value: str) -> str:
    """NFKC and case-fold text, collapsing whitespace while preserving punctuation."""
    folded = unicodedata.normalize("NFKC", _bounded(value)).casefold()
    return _bounded(" ".join(folded.split()))


def normalise_identifier(value: str) -> str:
    """NFKC and case-fold model/SKU text, removing only whitespace."""
    folded = unicodedata.normalize("NFKC", _bounded(value)).casefold()
    return _bounded("".join(folded.split()))


class MatchStatus(StrEnum):
    MATCHED = "matched"
    NOT_FOUND = "not_found"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class MatchResult:
    """Immutable canonical UUID candidates; status and identity are derived."""

    candidate_ids: tuple[UUID, ...] = ()

    def __post_init__(self) -> None:
        candidates = tuple(self.candidate_ids)
        if any(not isinstance(candidate, UUID) for candidate in candidates):
            raise TypeError("Canonical identities must be UUIDs")
        object.__setattr__(self, "candidate_ids", tuple(sorted(set(candidates))))

    @property
    def status(self) -> MatchStatus:
        match len(self.candidate_ids):
            case 0:
                return MatchStatus.NOT_FOUND
            case 1:
                return MatchStatus.MATCHED
            case _:
                return MatchStatus.AMBIGUOUS

    @property
    def canonical_id(self) -> UUID | None:
        return self.candidate_ids[0] if self.status == MatchStatus.MATCHED else None

    @classmethod
    def from_candidates(cls, candidates: Iterable[UUID]) -> "MatchResult":
        return cls(tuple(candidates))


class PurchaseChannel(StrEnum):
    ONLINE = "online"
    IN_STORE = "in_store"


_CHANNEL_ALIASES = {
    "online": PurchaseChannel.ONLINE,
    "web": PurchaseChannel.ONLINE,
    "website": PurchaseChannel.ONLINE,
    "in_store": PurchaseChannel.IN_STORE,
    "in-store": PurchaseChannel.IN_STORE,
    "instore": PurchaseChannel.IN_STORE,
    "store": PurchaseChannel.IN_STORE,
    "shop": PurchaseChannel.IN_STORE,
}


@dataclass(frozen=True, slots=True)
class ChannelMatchResult:
    channel: PurchaseChannel | None

    def __post_init__(self) -> None:
        if self.channel is not None:
            object.__setattr__(self, "channel", PurchaseChannel(self.channel))

    @property
    def status(self) -> MatchStatus:
        return MatchStatus.MATCHED if self.channel is not None else MatchStatus.NOT_FOUND


def resolve_purchase_channel(value: str) -> ChannelMatchResult:
    return ChannelMatchResult(_CHANNEL_ALIASES.get(normalise_text(value)))
