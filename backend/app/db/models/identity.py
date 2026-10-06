"""Curated identity reference data; PostgreSQL owns uniqueness and deletion integrity."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.models.core import Identity, Timestamps
from app.domain.identity_normalisation import normalise_identifier, normalise_text


class ManufacturerAlias(Base):
    __tablename__ = "manufacturer_aliases"
    __table_args__ = (
        CheckConstraint("length(trim(alias)) > 0", name="ck_manufacturer_aliases_alias_nonempty"),
        CheckConstraint(
            "length(trim(normalised_alias)) > 0",
            name="ck_manufacturer_aliases_normalised_nonempty",
        ),
    )
    manufacturer_id: Mapped[UUID] = mapped_column(
        ForeignKey("manufacturers.id", ondelete="CASCADE"), primary_key=True
    )
    alias: Mapped[str] = mapped_column(String(255))
    normalised_alias: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)


class RetailerAlias(Base):
    __tablename__ = "retailer_aliases"
    __table_args__ = (
        CheckConstraint("length(trim(alias)) > 0", name="ck_retailer_aliases_alias_nonempty"),
        CheckConstraint(
            "length(trim(normalised_alias)) > 0", name="ck_retailer_aliases_normalised_nonempty"
        ),
    )
    retailer_id: Mapped[UUID] = mapped_column(
        ForeignKey("retailers.id", ondelete="CASCADE"), primary_key=True
    )
    alias: Mapped[str] = mapped_column(String(255))
    normalised_alias: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)


class ProductModelAlias(Base):
    __tablename__ = "product_model_aliases"
    __table_args__ = (
        CheckConstraint("length(trim(alias)) > 0", name="ck_product_model_aliases_alias_nonempty"),
        CheckConstraint(
            "length(trim(normalised_alias)) > 0",
            name="ck_product_model_aliases_normalised_nonempty",
        ),
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    alias: Mapped[str] = mapped_column(String(255))
    normalised_alias: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)


class RetailerProductSku(Base):
    __tablename__ = "retailer_product_skus"
    __table_args__ = (
        CheckConstraint("length(trim(sku)) > 0", name="ck_retailer_product_skus_sku_nonempty"),
        CheckConstraint(
            "length(trim(normalised_sku)) > 0", name="ck_retailer_product_skus_normalised_nonempty"
        ),
        Index("ix_retailer_product_skus_retailer_sku", "retailer_id", "normalised_sku"),
    )
    retailer_id: Mapped[UUID] = mapped_column(
        ForeignKey("retailers.id", ondelete="RESTRICT"), primary_key=True
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), primary_key=True, index=True
    )
    sku: Mapped[str] = mapped_column(String(255))
    normalised_sku: Mapped[str] = mapped_column(String(255), primary_key=True)


class RetailerGroup(Identity, Timestamps, Base):
    __tablename__ = "retailer_groups"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_retailer_groups_slug"),
        CheckConstraint("length(trim(name)) > 0", name="ck_retailer_groups_name_nonempty"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="ck_retailer_groups_slug"),
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255))
    members: Mapped[list["RetailerGroupMember"]] = relationship(
        back_populates="group", passive_deletes="all"
    )


class RetailerGroupAlias(Base):
    __tablename__ = "retailer_group_aliases"
    __table_args__ = (
        CheckConstraint("length(trim(alias)) > 0", name="ck_retailer_group_aliases_alias_nonempty"),
        CheckConstraint(
            "length(trim(normalised_alias)) > 0",
            name="ck_retailer_group_aliases_normalised_nonempty",
        ),
    )
    retailer_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("retailer_groups.id", ondelete="CASCADE"), primary_key=True
    )
    alias: Mapped[str] = mapped_column(String(255))
    normalised_alias: Mapped[str] = mapped_column(String(255), primary_key=True, index=True)


class RetailerGroupMember(Base):
    __tablename__ = "retailer_group_members"
    retailer_group_id: Mapped[UUID] = mapped_column(
        ForeignKey("retailer_groups.id", ondelete="CASCADE"), primary_key=True
    )
    retailer_id: Mapped[UUID] = mapped_column(
        ForeignKey("retailers.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    group: Mapped[RetailerGroup] = relationship(back_populates="members")


def _normalise_alias(mapper, connection, target) -> None:
    # ORM writes derive keys on insert/update, including changes to the raw alias.
    # Direct SQL/bulk writers must supply keys from the same domain normaliser.
    normaliser = normalise_identifier if isinstance(target, ProductModelAlias) else normalise_text
    target.normalised_alias = normaliser(target.alias)


def _normalise_sku(mapper, connection, target: RetailerProductSku) -> None:
    target.normalised_sku = normalise_identifier(target.sku)


for _model in (ManufacturerAlias, RetailerAlias, ProductModelAlias, RetailerGroupAlias):
    event.listen(_model, "before_insert", _normalise_alias)
    event.listen(_model, "before_update", _normalise_alias)
event.listen(RetailerProductSku, "before_insert", _normalise_sku)
event.listen(RetailerProductSku, "before_update", _normalise_sku)
