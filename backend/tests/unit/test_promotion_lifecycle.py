from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime
from itertools import product
from uuid import uuid4

import pytest

from app.application.promotions import (
    PromotionConflict,
    PromotionNotFound,
    PromotionPersistenceError,
    PromotionPublicationError,
    PromotionRecord,
    change_promotion_status,
)
from app.domain.promotion_lifecycle import (
    InvalidPromotionTransition,
    validate_transition,
)
from app.domain.promotion_lifecycle import (
    PromotionStatus as S,
)
from app.domain.promotion_validation import ValidationSource
from tests.unit.test_promotion_provenance import sources
from tests.unit.test_promotion_validation import valid_snapshot

ALLOWED = {
    (S.DISCOVERED, S.EXTRACTED),
    (S.DISCOVERED, S.ARCHIVED),
    (S.EXTRACTED, S.REVIEW),
    (S.EXTRACTED, S.ARCHIVED),
    (S.REVIEW, S.EXTRACTED),
    (S.REVIEW, S.ACTIVE),
    (S.REVIEW, S.ARCHIVED),
    (S.ACTIVE, S.EXPIRED),
    (S.ACTIVE, S.ARCHIVED),
    (S.EXPIRED, S.ARCHIVED),
}


@pytest.mark.parametrize("previous,target", list(product(S, repeat=2)))
def test_complete_transition_matrix(previous, target):
    if previous == target:
        assert validate_transition(previous, target) is False
    elif (previous, target) in ALLOWED:
        assert validate_transition(previous, target) is True
    else:
        with pytest.raises(InvalidPromotionTransition) as error:
            validate_transition(previous, target)
        assert error.value.previous == previous
        assert error.value.target == target


def test_persisted_values():
    assert [s.value for s in S] == [
        "discovered",
        "extracted",
        "review",
        "active",
        "expired",
        "archived",
    ]
    with pytest.raises(ValueError):
        validate_transition(S.ACTIVE, "published")


class FakeRepository:
    def __init__(self, status=S.ACTIVE, stale=None, missing=False, failure=False):
        self.status, self.stale, self.missing, self.failure = status, stale, missing, failure
        self.writes = 0
        self.committed = False
        self.sources = sources()
        self.source_reads = 0

    def get_promotion(self, identity):
        if self.missing:
            return None
        now = datetime(2026, 10, 6, tzinfo=UTC)
        return PromotionRecord(
            identity, uuid4(), "Campaign", "campaign", self.status, None, None, now, now
        )

    def get_publication_snapshot_for_update(self, identity):
        self.source_reads += 1
        return replace(
            valid_snapshot(),
            sources=tuple(ValidationSource(s.source_id, s.role, s) for s in self.sources),
        )

    def list_promotion_sources(self, identity):
        self.source_reads += 1
        return self.sources

    def update_status(self, identity, expected, target):
        self.writes += 1
        if self.failure:
            raise PromotionPersistenceError("Write failed")
        if self.stale is not None:
            self.status = self.stale
            return False
        self.status = target
        return True

    @contextmanager
    def transaction(self):
        previous = self.status
        try:
            yield self
            self.committed = True
        except BaseException:
            self.status = previous
            raise


@pytest.mark.parametrize("status", list(S))
def test_application_no_op(status):
    repository = FakeRepository(status)
    result = change_promotion_status(repository.transaction, uuid4(), status)
    assert not result.changed
    assert repository.source_reads == 0
    assert repository.writes == 0
    assert repository.committed


@pytest.mark.parametrize("previous,target", sorted(ALLOWED))
def test_application_allowed(previous, target):
    repository = FakeRepository(previous)
    result = change_promotion_status(repository.transaction, uuid4(), target)
    assert result.changed
    assert result.previous_status == previous
    assert repository.status == target
    assert repository.committed


@pytest.mark.parametrize("stale", [S.EXPIRED, S.ARCHIVED])
def test_stale_reconciliation(stale):
    repository = FakeRepository(stale=stale)
    if stale == S.EXPIRED:
        assert not change_promotion_status(repository.transaction, uuid4(), S.EXPIRED).changed
    else:
        with pytest.raises(PromotionConflict):
            change_promotion_status(repository.transaction, uuid4(), S.EXPIRED)
        assert not repository.committed


@pytest.mark.parametrize(
    "case,error",
    [
        ("missing", PromotionNotFound),
        ("invalid", InvalidPromotionTransition),
        ("failure", PromotionPersistenceError),
    ],
)
def test_application_errors(case, error):
    repository = FakeRepository(missing=case == "missing", failure=case == "failure")
    with pytest.raises(error):
        change_promotion_status(
            repository.transaction, uuid4(), S.DISCOVERED if case == "invalid" else S.EXPIRED
        )
    assert repository.status == S.ACTIVE
    assert not repository.committed


def test_publication_rejection_precedes_write_and_retry_loads_current_sources():
    repository = FakeRepository(S.REVIEW)
    repository.sources = []
    with pytest.raises(PromotionPublicationError):
        change_promotion_status(repository.transaction, uuid4(), S.ACTIVE)
    assert repository.writes == 0
    assert repository.status == S.REVIEW
    assert not repository.committed
    repository.sources = sources()
    assert change_promotion_status(repository.transaction, uuid4(), S.ACTIVE).changed
    assert repository.source_reads == 2


@pytest.mark.parametrize("winner", [S.ACTIVE, S.ARCHIVED])
def test_publication_stale_reconciliation(winner):
    repository = FakeRepository(S.REVIEW, stale=winner)
    if winner == S.ACTIVE:
        assert not change_promotion_status(repository.transaction, uuid4(), S.ACTIVE).changed
    else:
        with pytest.raises(PromotionConflict):
            change_promotion_status(repository.transaction, uuid4(), S.ACTIVE)
    assert repository.source_reads == 1


@pytest.mark.parametrize("previous,target", sorted(ALLOWED - {(S.REVIEW, S.ACTIVE)}))
def test_other_transitions_do_not_read_incomplete_provenance(previous, target):
    repository = FakeRepository(previous)
    repository.sources = []
    assert change_promotion_status(repository.transaction, uuid4(), target).changed
    assert repository.source_reads == 0
