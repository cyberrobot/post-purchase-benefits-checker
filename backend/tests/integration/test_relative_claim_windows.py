from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.application.promotions import PromotionRecord
from app.db.models import Manufacturer, Promotion
from app.db.repositories.promotions import SqlAlchemyPromotionRepository
from app.domain.claim_windows import RelativeClaimWindow, evaluate_relative_claim_window
from app.domain.eligibility_result import ClaimWindowStatus
from app.domain.promotion_lifecycle import PromotionStatus

pytestmark = pytest.mark.integration


def promotion(start, end, *, fixed=False):
    return Promotion(
        manufacturer=Manufacturer(name="Example", slug="example"),
        name="Campaign",
        slug="campaign",
        status=PromotionStatus.EXPIRED,
        claim_start_offset_days=start,
        claim_end_offset_days=end,
        claim_start_date=date(2026, 11, 1) if fixed else None,
        claim_end_date=date(2026, 11, 30) if fixed else None,
    )


@pytest.mark.parametrize("start,end", [(0, 30), (30, 60), (30, 30), (0, 0), (None, None)])
def test_round_trip_and_repository_mapping(db_session, start, end):
    row = promotion(start, end)
    db_session.add(row)
    db_session.flush()
    identity = row.id
    db_session.expunge_all()
    loaded = db_session.get(Promotion, identity)
    assert (loaded.claim_start_offset_days, loaded.claim_end_offset_days) == (start, end)
    repository = SqlAlchemyPromotionRepository(db_session)
    record = repository.get_promotion(identity)
    assert isinstance(record, PromotionRecord)
    assert (record.claim_start_offset_days, record.claim_end_offset_days) == (start, end)
    assert record.claim_start_date is record.claim_end_date is None
    assert repository.list_promotions() == [record]
    assert repository.list_historical_promotions() == [record]
    if start is not None:
        assert type(record.claim_start_offset_days) is type(record.claim_end_offset_days) is int
        window = RelativeClaimWindow(record.claim_start_offset_days, record.claim_end_offset_days)
        result = evaluate_relative_claim_window(window, date(2026, 10, 1), date(2026, 10, 1))
        assert result.status is (
            ClaimWindowStatus.OPEN if start == 0 else ClaimWindowStatus.NOT_YET_OPEN
        )
        assert db_session.get(Promotion, identity).status == PromotionStatus.EXPIRED


@pytest.mark.parametrize(
    "start,end,fixed,constraint",
    [
        (0, None, False, "ck_promotions_claim_offset_days_complete"),
        (None, 30, False, "ck_promotions_claim_offset_days_complete"),
        (-1, 30, False, "ck_promotions_claim_offset_days_nonnegative"),
        (-2, -1, False, "ck_promotions_claim_offset_days_nonnegative"),
        (60, 30, False, "ck_promotions_claim_offset_days"),
        (30, 60, True, "ck_promotions_claim_window_single_type"),
    ],
)
def test_database_rejects_invalid_windows(db_session, start, end, fixed, constraint):
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.add(promotion(start, end, fixed=fixed))
        db_session.flush()
    assert error.value.orig.diag.constraint_name == constraint


@pytest.mark.parametrize(
    "changes,constraint",
    [
        ({"claim_start_offset_days": None}, "ck_promotions_claim_offset_days_complete"),
        ({"claim_end_offset_days": None}, "ck_promotions_claim_offset_days_complete"),
        ({"claim_start_offset_days": -1}, "ck_promotions_claim_offset_days_nonnegative"),
        ({"claim_start_offset_days": 61}, "ck_promotions_claim_offset_days"),
        (
            {"claim_start_date": date(2026, 11, 1), "claim_end_date": date(2026, 11, 30)},
            "ck_promotions_claim_window_single_type",
        ),
    ],
)
def test_invalid_update_rolls_back_atomically(db_session, changes, constraint):
    row = promotion(30, 60)
    db_session.add(row)
    db_session.flush()
    identity = row.id
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        for field, value in changes.items():
            setattr(row, field, value)
        db_session.flush()
    assert error.value.orig.diag.constraint_name == constraint
    db_session.expire_all()
    record = SqlAlchemyPromotionRepository(db_session).get_promotion(identity)
    assert (record.claim_start_offset_days, record.claim_end_offset_days) == (30, 60)
    assert record.claim_start_date is record.claim_end_date is None


def test_fixed_only_remains_valid(db_session):
    row = promotion(None, None, fixed=True)
    db_session.add(row)
    db_session.flush()
    record = SqlAlchemyPromotionRepository(db_session).get_promotion(row.id)
    assert (record.claim_start_date, record.claim_end_date) == (
        date(2026, 11, 1),
        date(2026, 11, 30),
    )
    assert record.claim_start_offset_days is record.claim_end_offset_days is None
