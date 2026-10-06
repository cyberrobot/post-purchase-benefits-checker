from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.promotion_provenance import (
    PromotionProvenanceError,
    PromotionSourceRecord,
    SourceRole,
    SourceType,
    validate_publication_provenance,
)

NOW = datetime(2026, 10, 6, tzinfo=UTC)


def sources():
    return [
        PromotionSourceRecord(uuid4(), role, "https://example.test/promo", SourceType.PDF, NOW, NOW)
        for role in (SourceRole.PRIMARY, SourceRole.CLAIM)
    ]


def test_values_and_valid_view():
    assert [t.value for t in SourceType] == ["web_page", "pdf", "other"]
    assert [r.value for r in SourceRole] == ["primary", "terms", "claim", "supporting"]
    records = sources()
    view = validate_publication_provenance(reversed(records))
    assert view.official_source_url == view.claim_url == records[0].url
    assert view.source_type == SourceType.PDF
    assert view.retrieved_at == view.verified_at == NOW
    with pytest.raises(FrozenInstanceError):
        records[0].url = "changed"


@pytest.mark.parametrize("role", [SourceRole.PRIMARY, SourceRole.CLAIM])
@pytest.mark.parametrize("case", ["missing", "ambiguous", "unverified"])
def test_required_roles(role, case):
    records = sources()
    selected = next(s for s in records if s.role == role)
    if case == "missing":
        records.remove(selected)
        # Other evidence must not substitute for a required role.
        records.extend(replace(selected, role=r) for r in (SourceRole.TERMS, SourceRole.SUPPORTING))
        reason = f"missing_{role}_source"
    elif case == "ambiguous":
        records.append(replace(selected, source_id=uuid4()))
        reason = f"ambiguous_{role}_source"
    else:
        records[records.index(selected)] = replace(selected, verified_at=None)
        reason = f"{role}_source_unverified"
    for order in (records, list(reversed(records))):
        with pytest.raises(PromotionProvenanceError) as error:
            validate_publication_provenance(order)
        assert error.value.reason_code == reason


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    "url",
    [
        None,
        123,
        "",
        "  ",
        "relative/path",
        "example.test/path",
        "ftp://example.test/file",
        "https://",
        "https://[bad",
        "https://example.test:bad",
        "https://exa mple.test",
    ],
)
def test_invalid_urls(index, url):
    records = sources()
    records[index] = replace(records[index], url=url)
    with pytest.raises(PromotionProvenanceError) as error:
        validate_publication_provenance(records)
    assert error.value.reason_code == f"invalid_{records[index].role}_url"


@pytest.mark.parametrize("index", [0, 1])
@pytest.mark.parametrize(
    "field,value,reason",
    [
        ("retrieved_at", None, "invalid_retrieval_timestamp"),
        ("retrieved_at", NOW.replace(tzinfo=None), "invalid_retrieval_timestamp"),
        ("verified_at", NOW.replace(tzinfo=None), "invalid_verification_timestamp"),
        ("verified_at", NOW - timedelta(seconds=1), "invalid_verification_timestamp"),
        ("verified_at", "2026-10-06", "invalid_verification_timestamp"),
    ],
)
def test_invalid_timestamps(index, field, value, reason):
    records = sources()
    records[index] = replace(records[index], **{field: value})
    with pytest.raises(PromotionProvenanceError) as error:
        validate_publication_provenance(records)
    assert error.value.reason_code == reason


@pytest.mark.parametrize("value", ["unsupported", "PDF", "", None])
def test_unsupported_type(value):
    with pytest.raises(PromotionProvenanceError) as error:
        replace(sources()[0], source_type=value)
    assert error.value.reason_code == "unsupported_source_type"


@pytest.mark.parametrize("kind", list(SourceType))
def test_supported_types_and_timezone_offsets(kind):
    records = [
        replace(s, source_type=kind, verified_at=NOW.astimezone(timezone(timedelta(hours=1))))
        for s in sources()
    ]
    assert validate_publication_provenance(records).source_type == kind
