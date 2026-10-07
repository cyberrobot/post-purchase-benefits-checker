"""Core promotion persistence mappings; no eligibility or publication behaviour."""

from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Identity:
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# Let PostgreSQL handle deletes even for loaded collections: ORM nulling or
# unlinking would bypass reference restrictions. Expire/reload after a cascade.
# Composite uniqueness/primary-key indexes cover their leading foreign keys.
class Manufacturer(Identity, Timestamps, Base):
    __tablename__ = "manufacturers"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_manufacturers_slug"),
        CheckConstraint("length(trim(name)) > 0", name="ck_manufacturers_name_nonempty"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_manufacturers_slug"),
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255))
    products: Mapped[list["Product"]] = relationship(
        back_populates="manufacturer", passive_deletes="all"
    )
    promotions: Mapped[list["Promotion"]] = relationship(
        back_populates="manufacturer", passive_deletes="all"
    )


class Product(Identity, Timestamps, Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("manufacturer_id", "slug", name="uq_products_manufacturer_slug"),
        CheckConstraint("length(trim(name)) > 0", name="ck_products_name_nonempty"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_products_slug"),
    )
    manufacturer_id: Mapped[UUID] = mapped_column(
        ForeignKey("manufacturers.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255))
    model_number: Mapped[str | None] = mapped_column(String(255))
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="products")
    variant_links: Mapped[list["PromotionVariantProduct"]] = relationship(
        back_populates="product", passive_deletes="all"
    )


class Retailer(Identity, Timestamps, Base):
    __tablename__ = "retailers"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_retailers_slug"),
        CheckConstraint("length(trim(name)) > 0", name="ck_retailers_name_nonempty"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_retailers_slug"),
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255))
    variants: Mapped[list["PromotionVariant"]] = relationship(
        back_populates="retailer", passive_deletes="all"
    )


class Promotion(Identity, Timestamps, Base):
    __tablename__ = "promotions"
    __table_args__ = (
        UniqueConstraint("manufacturer_id", "slug", name="uq_promotions_manufacturer_slug"),
        CheckConstraint(
            "status IN ('discovered','extracted','review','active','expired','archived')",
            name="ck_promotions_status",
        ),
        CheckConstraint(
            "purchase_start_date <= purchase_end_date", name="ck_promotions_purchase_dates"
        ),
        CheckConstraint(
            "(claim_start_date IS NULL AND claim_end_date IS NULL) OR "
            "(claim_start_date IS NOT NULL AND claim_end_date IS NOT NULL)",
            name="ck_promotions_claim_dates_complete",
        ),
        CheckConstraint("claim_start_date <= claim_end_date", name="ck_promotions_claim_dates"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_promotions_slug"),
    )
    manufacturer_id: Mapped[UUID] = mapped_column(
        ForeignKey("manufacturers.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32))
    purchase_start_date: Mapped[date | None] = mapped_column(Date)
    purchase_end_date: Mapped[date | None] = mapped_column(Date)
    claim_start_date: Mapped[date | None] = mapped_column(Date)
    claim_end_date: Mapped[date | None] = mapped_column(Date)
    manufacturer: Mapped["Manufacturer"] = relationship(back_populates="promotions")
    variants: Mapped[list["PromotionVariant"]] = relationship(
        back_populates="promotion", passive_deletes="all"
    )
    source_links: Mapped[list["PromotionSource"]] = relationship(
        back_populates="promotion", passive_deletes="all"
    )


class PromotionVariant(Identity, Timestamps, Base):
    __tablename__ = "promotion_variants"
    __table_args__ = (
        UniqueConstraint("promotion_id", "code", name="uq_promotion_variants_promotion_code"),
    )
    promotion_id: Mapped[UUID] = mapped_column(ForeignKey("promotions.id", ondelete="CASCADE"))
    retailer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("retailers.id", ondelete="RESTRICT"), index=True
    )
    code: Mapped[str] = mapped_column(String(255))
    name: Mapped[str | None] = mapped_column(String(255))
    promotion: Mapped["Promotion"] = relationship(back_populates="variants")
    retailer: Mapped["Retailer | None"] = relationship(back_populates="variants")
    product_links: Mapped[list["PromotionVariantProduct"]] = relationship(
        back_populates="variant", passive_deletes="all"
    )
    benefits: Mapped[list["Benefit"]] = relationship(
        back_populates="variant", passive_deletes="all"
    )
    requirements: Mapped[list["Requirement"]] = relationship(
        back_populates="variant", passive_deletes="all"
    )


class Benefit(Identity, Timestamps, Base):
    __tablename__ = "benefits"
    __table_args__ = (
        CheckConstraint(
            "benefit_type IN ('cashback','extended_warranty','free_gift')", name="ck_benefits_type"
        ),
    )
    promotion_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("promotion_variants.id", ondelete="CASCADE"), index=True
    )
    benefit_type: Mapped[str] = mapped_column(String(32))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    variant: Mapped["PromotionVariant"] = relationship(back_populates="benefits")


class Requirement(Identity, Timestamps, Base):
    __tablename__ = "requirements"
    __table_args__ = (
        CheckConstraint(
            "requirement_type IN ('receipt','serial_number','registration',"
            "'invoice','barcode','imei')",
            name="ck_requirements_type",
        ),
    )
    promotion_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("promotion_variants.id", ondelete="CASCADE"), index=True
    )
    requirement_type: Mapped[str] = mapped_column(String(32))
    description: Mapped[str | None] = mapped_column(Text)
    variant: Mapped["PromotionVariant"] = relationship(back_populates="requirements")


class Source(Identity, Base):
    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint("source_type IN ('web_page','pdf','other')", name="ck_sources_type"),
        CheckConstraint("verified_at >= retrieved_at", name="ck_sources_verification_dates"),
    )
    url: Mapped[str] = mapped_column(String(2048))
    source_type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str | None] = mapped_column(String(255))
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    promotion_links: Mapped[list["PromotionSource"]] = relationship(
        back_populates="source", passive_deletes="all"
    )


class PromotionVariantProduct(Base):
    __tablename__ = "promotion_variant_products"
    promotion_variant_id: Mapped[UUID] = mapped_column(
        ForeignKey("promotion_variants.id", ondelete="CASCADE"), primary_key=True
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    variant: Mapped[PromotionVariant] = relationship(back_populates="product_links")
    product: Mapped[Product] = relationship(back_populates="variant_links")


class PromotionSource(Base):
    __tablename__ = "promotion_sources"
    __table_args__ = (
        CheckConstraint(
            "role IN ('primary','terms','claim','supporting')", name="ck_promotion_sources_role"
        ),
    )
    promotion_id: Mapped[UUID] = mapped_column(
        ForeignKey("promotions.id", ondelete="CASCADE"), primary_key=True
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    role: Mapped[str] = mapped_column(String(32))
    promotion: Mapped[Promotion] = relationship(back_populates="source_links")
    source: Mapped[Source] = relationship(back_populates="promotion_links")
