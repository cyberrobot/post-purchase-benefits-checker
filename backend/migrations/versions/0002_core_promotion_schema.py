"""Create the core promotion schema."""

import sqlalchemy as sa
from alembic import op

revision = "0002_core_promotion_schema"
down_revision = "0001_initial_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "manufacturers",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_manufacturers_slug"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_manufacturers_name_nonempty"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_manufacturers_slug"),
    )
    op.create_table(
        "retailers",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_retailers_slug"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_retailers_name_nonempty"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_retailers_slug"),
    )
    op.create_table(
        "sources",
        sa.Column("url", sa.String(length=2048), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("source_type IN ('web_page','pdf','other')", name="ck_sources_type"),
        sa.CheckConstraint("verified_at >= retrieved_at", name="ck_sources_verification_dates"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "products",
        sa.Column("manufacturer_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("model_number", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_products_slug"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_products_name_nonempty"),
        sa.ForeignKeyConstraint(["manufacturer_id"], ["manufacturers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manufacturer_id", "slug", name="uq_products_manufacturer_slug"),
    )
    op.create_table(
        "promotions",
        sa.Column("manufacturer_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("purchase_start_date", sa.Date(), nullable=True),
        sa.Column("purchase_end_date", sa.Date(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_promotions_slug"),
        sa.CheckConstraint(
            "status IN ('discovered','extracted','review','active','expired','archived')",
            name="ck_promotions_status",
        ),
        sa.CheckConstraint(
            "purchase_start_date <= purchase_end_date", name="ck_promotions_purchase_dates"
        ),
        sa.ForeignKeyConstraint(["manufacturer_id"], ["manufacturers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("manufacturer_id", "slug", name="uq_promotions_manufacturer_slug"),
    )
    op.create_table(
        "promotion_sources",
        sa.Column("promotion_id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.CheckConstraint(
            "role IN ('primary','terms','claim','supporting')", name="ck_promotion_sources_role"
        ),
        sa.ForeignKeyConstraint(["promotion_id"], ["promotions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("promotion_id", "source_id"),
    )
    op.create_index(
        op.f("ix_promotion_sources_source_id"), "promotion_sources", ["source_id"], unique=False
    )
    op.create_table(
        "promotion_variants",
        sa.Column("promotion_id", sa.Uuid(), nullable=False),
        sa.Column("retailer_id", sa.Uuid(), nullable=True),
        sa.Column("code", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.ForeignKeyConstraint(["promotion_id"], ["promotions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["retailer_id"], ["retailers.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("promotion_id", "code", name="uq_promotion_variants_promotion_code"),
    )
    op.create_index(
        op.f("ix_promotion_variants_retailer_id"),
        "promotion_variants",
        ["retailer_id"],
        unique=False,
    )
    op.create_table(
        "benefits",
        sa.Column("promotion_variant_id", sa.Uuid(), nullable=False),
        sa.Column("benefit_type", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "benefit_type IN ('cashback','extended_warranty','free_gift')", name="ck_benefits_type"
        ),
        sa.ForeignKeyConstraint(
            ["promotion_variant_id"], ["promotion_variants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_benefits_promotion_variant_id"), "benefits", ["promotion_variant_id"], unique=False
    )
    op.create_table(
        "promotion_variant_products",
        sa.Column("promotion_variant_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["promotion_variant_id"], ["promotion_variants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("promotion_variant_id", "product_id"),
    )
    op.create_index(
        op.f("ix_promotion_variant_products_product_id"),
        "promotion_variant_products",
        ["product_id"],
        unique=False,
    )
    op.create_table(
        "requirements",
        sa.Column("promotion_variant_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_type", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
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
        sa.CheckConstraint(
            "requirement_type IN ('receipt','serial_number','registration',"
            "'invoice','barcode','imei')",
            name="ck_requirements_type",
        ),
        sa.ForeignKeyConstraint(
            ["promotion_variant_id"], ["promotion_variants.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_requirements_promotion_variant_id"),
        "requirements",
        ["promotion_variant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("requirements")
    op.drop_table("promotion_variant_products")
    op.drop_table("benefits")
    op.drop_table("promotion_variants")
    op.drop_table("promotion_sources")
    op.drop_table("promotions")
    op.drop_table("products")
    op.drop_table("sources")
    op.drop_table("retailers")
    op.drop_table("manufacturers")
