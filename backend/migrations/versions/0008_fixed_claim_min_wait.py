"""Allow a fixed campaign window to include a purchase-specific minimum wait.

Existing rows retain NULL (no additional wait). Deploy the evaluator before enabling
wait-bearing data; old application versions ignore the new field. Verified legacy
promotions require explicit source-backed backfill, never inference from brand.
"""

import sqlalchemy as sa
from alembic import op

revision = "0008_fixed_claim_min_wait"
down_revision = "0007_reward_calculation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("promotions", sa.Column("claim_min_wait_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_promotions_claim_min_wait",
        "promotions",
        "claim_min_wait_days IS NULL OR (claim_start_date IS NOT NULL "
        "AND claim_min_wait_days BETWEEN 0 AND 3652058)",
    )


def downgrade() -> None:
    # Refuse a rollback that would silently remove a published eligibility condition.
    op.execute(
        "DO $$ BEGIN IF EXISTS (SELECT 1 FROM promotions WHERE claim_min_wait_days IS NOT NULL) "
        "THEN RAISE EXCEPTION 'Remove wait-bearing promotion data before downgrade'; "
        "END IF; END $$"
    )
    op.drop_constraint("ck_promotions_claim_min_wait", "promotions", type_="check")
    op.drop_column("promotions", "claim_min_wait_days")
