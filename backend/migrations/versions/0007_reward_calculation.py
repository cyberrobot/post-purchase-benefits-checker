"""Add composed structured GBP reward definitions without backfilling benefits."""

import sqlalchemy as sa
from alembic import op

revision = "0007_reward_calculation"
down_revision = "0006_promotion_requirements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "benefit_rewards",
        sa.Column("benefit_id", sa.Uuid(), nullable=False),
        sa.Column("reward_type", sa.String(32), nullable=False),
        sa.Column("fixed_amount", sa.Numeric(), nullable=True),
        sa.Column("percentage", sa.Numeric(), nullable=True),
        sa.PrimaryKeyConstraint("benefit_id"),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefits.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "reward_type IN ('fixed_amount','percentage','product_specific')",
            name="ck_benefit_rewards_type",
        ),
        sa.CheckConstraint(
            "(reward_type = 'fixed_amount' AND fixed_amount IS NOT NULL AND percentage IS NULL) OR "
            "(reward_type = 'percentage' AND fixed_amount IS NULL AND percentage IS NOT NULL) OR "
            "(reward_type = 'product_specific' AND fixed_amount IS NULL AND percentage IS NULL)",
            name="ck_benefit_rewards_shape",
        ),
        sa.CheckConstraint(
            "fixed_amount > 0 AND fixed_amount < 'Infinity'::numeric AND scale(fixed_amount) <= 2",
            name="ck_benefit_rewards_amount",
        ),
        sa.CheckConstraint(
            "percentage > 0 AND percentage <= 100 AND scale(percentage) <= 4",
            name="ck_benefit_rewards_percentage",
        ),
    )
    op.create_table(
        "benefit_product_reward_values",
        sa.Column("benefit_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(), nullable=False),
        sa.PrimaryKeyConstraint("benefit_id", "product_id"),
        sa.ForeignKeyConstraint(["benefit_id"], ["benefit_rewards.benefit_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.CheckConstraint(
            "amount > 0 AND amount < 'Infinity'::numeric AND scale(amount) <= 2",
            name="ck_benefit_product_reward_values_amount",
        ),
    )
    op.create_index(
        "ix_benefit_product_reward_values_product_id",
        "benefit_product_reward_values",
        ["product_id"],
    )


def downgrade() -> None:
    # Prevent a concurrent insert between the emptiness check and table removal.
    # PostgreSQL transactional DDL retains schema, constraints and revision on refusal.
    op.execute("LOCK TABLE benefit_rewards, benefit_product_reward_values IN ACCESS EXCLUSIVE MODE")
    if op.get_bind().execute(sa.text("SELECT EXISTS (SELECT 1 FROM benefit_rewards)")).scalar():
        raise RuntimeError("Cannot downgrade reward calculation while reward definitions exist")
    op.drop_table("benefit_product_reward_values")
    op.drop_table("benefit_rewards")
