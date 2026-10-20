"""Compatibility imports for the shared reviewed reference pack."""

from app.application.promotions import change_promotion_status
from app.db.reference.samsung import (  # noqa: F401
    construct_reference,
    reference_manifest,
    validate_manifest,
)
from app.domain.promotion_lifecycle import PromotionStatus as S


def finish_reference(transaction_factory, promotion_id):
    """Resume review/active safely; expired replays do not republish or edit evidence."""
    with transaction_factory() as repository:
        status = repository.get_promotion(promotion_id).status
    if status == S.REVIEW:
        change_promotion_status(transaction_factory, promotion_id, S.ACTIVE)
    if status in (S.REVIEW, S.ACTIVE):
        change_promotion_status(transaction_factory, promotion_id, S.EXPIRED)
