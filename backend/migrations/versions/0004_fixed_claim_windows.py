"""Add optional complete fixed claim dates without changing existing promotions."""

import sqlalchemy as sa
from alembic import op

revision = "0004_fixed_claim_windows"
down_revision = "0003_identity_normalisation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("promotions", sa.Column("claim_start_date", sa.Date(), nullable=True))
    op.add_column("promotions", sa.Column("claim_end_date", sa.Date(), nullable=True))
    op.create_check_constraint(
        "ck_promotions_claim_dates_complete",
        "promotions",
        "(claim_start_date IS NULL AND claim_end_date IS NULL) OR "
        "(claim_start_date IS NOT NULL AND claim_end_date IS NOT NULL)",
    )
    op.create_check_constraint(
        "ck_promotions_claim_dates", "promotions", "claim_start_date <= claim_end_date"
    )


def downgrade() -> None:
    op.drop_constraint("ck_promotions_claim_dates", "promotions", type_="check")
    op.drop_constraint("ck_promotions_claim_dates_complete", "promotions", type_="check")
    op.drop_column("promotions", "claim_end_date")
    op.drop_column("promotions", "claim_start_date")
