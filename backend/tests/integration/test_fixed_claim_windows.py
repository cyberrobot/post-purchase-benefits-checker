from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.application.promotions import PromotionRecord
from app.db.models import Manufacturer, Promotion
from app.db.repositories.promotions import SqlAlchemyPromotionRepository
from app.domain.claim_windows import FixedClaimWindow, evaluate_fixed_claim_window
from app.domain.eligibility_result import ClaimWindowStatus
from app.domain.promotion_lifecycle import PromotionStatus

pytestmark = pytest.mark.integration
START, END = date(2026, 11, 1), date(2026, 11, 30)


def promotion(start, end):
    return Promotion(
        manufacturer=Manufacturer(name="Example", slug="example"),
        name="Campaign",
        slug="campaign",
        status=PromotionStatus.EXPIRED,
        purchase_start_date=date(2026, 10, 1),
        purchase_end_date=date(2026, 10, 31),
        claim_start_date=start,
        claim_end_date=end,
    )


@pytest.mark.parametrize("start,end", [(START, END), (None, None), (END, END)])
def test_round_trip_and_repository_mapping(db_session, start, end):
    row = promotion(start, end)
    db_session.add(row)
    db_session.flush()
    identity = row.id
    db_session.expunge_all()
    loaded = db_session.get(Promotion, identity)
    assert (loaded.claim_start_date, loaded.claim_end_date) == (start, end)
    repository = SqlAlchemyPromotionRepository(db_session)
    record = repository.get_promotion(identity)
    assert isinstance(record, PromotionRecord)
    assert (record.claim_start_date, record.claim_end_date) == (start, end)
    assert repository.list_promotions() == [record]
    assert repository.list_historical_promotions() == [record]
    assert record.status is PromotionStatus.EXPIRED
    if start is not None:
        # Historical publication is independent of claim timing.
        window = FixedClaimWindow(record.claim_start_date, record.claim_end_date)
        assert evaluate_fixed_claim_window(window, start).status is ClaimWindowStatus.OPEN
        assert db_session.get(Promotion, identity).status == PromotionStatus.EXPIRED
    else:
        assert record.claim_start_date is record.claim_end_date is None


@pytest.mark.parametrize(
    "start,end,constraint",
    [
        (START, None, "ck_promotions_claim_dates_complete"),
        (None, END, "ck_promotions_claim_dates_complete"),
        (END, START, "ck_promotions_claim_dates"),
    ],
)
def test_database_rejects_invalid_windows(db_session, start, end, constraint):
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.add(promotion(start, end))
        db_session.flush()
    assert error.value.orig.diag.constraint_name == constraint


@pytest.mark.parametrize("field", ["claim_start_date", "claim_end_date"])
def test_database_rejects_partial_update_atomically(db_session, field):
    row = promotion(START, END)
    db_session.add(row)
    db_session.flush()
    identity = row.id
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        setattr(row, field, None)
        db_session.flush()
    assert error.value.orig.diag.constraint_name == "ck_promotions_claim_dates_complete"
    db_session.expire_all()
    record = SqlAlchemyPromotionRepository(db_session).get_promotion(identity)
    assert (record.claim_start_date, record.claim_end_date) == (START, END)
