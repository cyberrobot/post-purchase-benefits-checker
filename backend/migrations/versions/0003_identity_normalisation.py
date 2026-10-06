"""Add curated product and retailer identity reference data without backfilling aliases."""

import sqlalchemy as sa
from alembic import op

revision = "0003_identity_normalisation"
down_revision = "0002_core_promotion_schema"
branch_labels = None
depends_on = None


def _create_alias_table(table: str, owner: str, reference: str) -> None:
    op.create_table(
        table,
        sa.Column(owner, sa.Uuid(), nullable=False),
        sa.Column("alias", sa.String(255), nullable=False),
        sa.Column("normalised_alias", sa.String(255), nullable=False),
        sa.ForeignKeyConstraint([owner], [f"{reference}.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint(owner, "normalised_alias"),
        sa.CheckConstraint("length(trim(alias)) > 0", name=f"ck_{table}_alias_nonempty"),
        sa.CheckConstraint(
            "length(trim(normalised_alias)) > 0", name=f"ck_{table}_normalised_nonempty"
        ),
    )
    op.create_index(f"ix_{table}_normalised_alias", table, ["normalised_alias"])


def upgrade() -> None:
    op.create_table(
        "retailer_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_retailer_groups_slug"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_retailer_groups_name_nonempty"),
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_retailer_groups_slug"),
    )
    _create_alias_table("manufacturer_aliases", "manufacturer_id", "manufacturers")
    _create_alias_table("retailer_aliases", "retailer_id", "retailers")
    _create_alias_table("product_model_aliases", "product_id", "products")
    _create_alias_table("retailer_group_aliases", "retailer_group_id", "retailer_groups")
    op.create_table(
        "retailer_product_skus",
        sa.Column("retailer_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.Column("sku", sa.String(255), nullable=False),
        sa.Column("normalised_sku", sa.String(255), nullable=False),
        sa.PrimaryKeyConstraint("retailer_id", "product_id", "normalised_sku"),
        sa.ForeignKeyConstraint(["retailer_id"], ["retailers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("length(trim(sku)) > 0", name="ck_retailer_product_skus_sku_nonempty"),
        sa.CheckConstraint(
            "length(trim(normalised_sku)) > 0", name="ck_retailer_product_skus_normalised_nonempty"
        ),
    )
    op.create_index("ix_retailer_product_skus_product_id", "retailer_product_skus", ["product_id"])
    op.create_index(
        "ix_retailer_product_skus_retailer_sku",
        "retailer_product_skus",
        ["retailer_id", "normalised_sku"],
    )
    op.create_table(
        "retailer_group_members",
        sa.Column("retailer_group_id", sa.Uuid(), nullable=False),
        sa.Column("retailer_id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("retailer_group_id", "retailer_id"),
        sa.ForeignKeyConstraint(["retailer_group_id"], ["retailer_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retailer_id"], ["retailers.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_retailer_group_members_retailer_id", "retailer_group_members", ["retailer_id"]
    )


def downgrade() -> None:
    op.drop_table("retailer_group_members")
    op.drop_table("retailer_product_skus")
    op.drop_table("retailer_group_aliases")
    op.drop_table("product_model_aliases")
    op.drop_table("retailer_aliases")
    op.drop_table("manufacturer_aliases")
    op.drop_table("retailer_groups")
