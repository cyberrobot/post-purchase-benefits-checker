"""Add optional purchase-relative claim offsets, exclusive of fixed dates."""

import sqlalchemy as sa
from alembic import op

revision = "0005_relative_claim_windows"
down_revision = "0004_fixed_claim_windows"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("promotions", sa.Column("claim_start_offset_days", sa.Integer(), nullable=True))
    op.add_column("promotions", sa.Column("claim_end_offset_days", sa.Integer(), nullable=True))
    op.create_check_constraint(
        "ck_promotions_claim_offset_days_complete",
        "promotions",
        "(claim_start_offset_days IS NULL AND claim_end_offset_days IS NULL) OR "
        "(claim_start_offset_days IS NOT NULL AND claim_end_offset_days IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_promotions_claim_offset_days_nonnegative",
        "promotions",
        "claim_start_offset_days >= 0 AND claim_end_offset_days >= 0",
    )
    op.create_check_constraint(
        "ck_promotions_claim_offset_days",
        "promotions",
        "claim_start_offset_days <= claim_end_offset_days",
    )
    op.create_check_constraint(
        "ck_promotions_claim_window_single_type",
        "promotions",
        "NOT (claim_start_date IS NOT NULL AND claim_start_offset_days IS NOT NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_promotions_claim_window_single_type", "promotions", type_="check")
    op.drop_constraint("ck_promotions_claim_offset_days", "promotions", type_="check")
    op.drop_constraint("ck_promotions_claim_offset_days_nonnegative", "promotions", type_="check")
    op.drop_constraint("ck_promotions_claim_offset_days_complete", "promotions", type_="check")
    op.drop_column("promotions", "claim_end_offset_days")
    op.drop_column("promotions", "claim_start_offset_days")
