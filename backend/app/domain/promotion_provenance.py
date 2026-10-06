"""Deterministic publication evidence validation; never retrieves URLs."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import UUID


class SourceType(StrEnum):
    WEB_PAGE = "web_page"
    PDF = "pdf"
    OTHER = "other"


class SourceRole(StrEnum):
    PRIMARY = "primary"
    TERMS = "terms"
    CLAIM = "claim"
    SUPPORTING = "supporting"


class PromotionProvenanceError(ValueError):
    def __init__(self, reason_code: str):
        self.reason_code = reason_code
        super().__init__(reason_code)


@dataclass(frozen=True)
class PromotionSourceRecord:
    source_id: UUID
    role: SourceRole
    url: str
    source_type: SourceType
    retrieved_at: datetime
    verified_at: datetime | None

    def __post_init__(self):
        try:
            object.__setattr__(self, "role", SourceRole(self.role))
        except (ValueError, TypeError):
            raise PromotionProvenanceError("unsupported_source_role") from None
        try:
            object.__setattr__(self, "source_type", SourceType(self.source_type))
        except (ValueError, TypeError):
            raise PromotionProvenanceError("unsupported_source_type") from None


@dataclass(frozen=True)
class PublishedProvenance:
    official_source_url: str
    source_type: SourceType
    retrieved_at: datetime
    verified_at: datetime
    claim_url: str


def _aware(value: object) -> bool:
    return (
        isinstance(value, datetime) and value.tzinfo is not None and value.utcoffset() is not None
    )


def _validate_source(source: PromotionSourceRecord) -> None:
    role = source.role.value
    valid_url = False
    if isinstance(source.url, str):
        url = source.url.strip()
        try:
            parsed = urlsplit(url)
            valid_url = (
                bool(url)
                and not any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in url)
                and parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and parsed.username is None
                and parsed.password is None
                and parsed.port != 0
            )
        except ValueError:
            pass
    if not valid_url:
        raise PromotionProvenanceError(f"invalid_{role}_url")
    if not _aware(source.retrieved_at):
        raise PromotionProvenanceError("invalid_retrieval_timestamp")
    if source.verified_at is None:
        raise PromotionProvenanceError(f"{role}_source_unverified")
    if not _aware(source.verified_at) or source.verified_at < source.retrieved_at:
        raise PromotionProvenanceError("invalid_verification_timestamp")


def validate_publication_provenance(
    sources: Iterable[PromotionSourceRecord],
) -> PublishedProvenance:
    """Require unique curated primary and claim associations, without inferring officiality."""
    records = tuple(sources)
    required = {}
    for role in (SourceRole.PRIMARY, SourceRole.CLAIM):
        matches = [source for source in records if source.role == role]
        if not matches:
            raise PromotionProvenanceError(f"missing_{role.value}_source")
        if len(matches) != 1:
            raise PromotionProvenanceError(f"ambiguous_{role.value}_source")
        required[role] = matches[0]
    for source in required.values():
        _validate_source(source)
    primary, claim = required[SourceRole.PRIMARY], required[SourceRole.CLAIM]
    return PublishedProvenance(
        primary.url, primary.source_type, primary.retrieved_at, primary.verified_at, claim.url
    )
