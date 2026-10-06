"""Read-only SQLAlchemy reference queries returning UUIDs, never ORM rows."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.application.identity_matching import IdentityPersistenceError
from app.db.models import (
    Manufacturer,
    ManufacturerAlias,
    Product,
    ProductModelAlias,
    Retailer,
    RetailerAlias,
    RetailerGroup,
    RetailerGroupAlias,
    RetailerGroupMember,
    RetailerProductSku,
)
from app.domain.identity_normalisation import normalise_identifier, normalise_text


class SqlAlchemyIdentityRepository:
    """Caller owns the read transaction. Matching never flushes pending ORM writes."""

    def __init__(self, session: Session):
        self.session = session

    def _named_candidates(
        self, canonical, alias, owner_column, normalised: str
    ) -> tuple[UUID, ...]:
        try:
            with self.session.no_autoflush:
                # Small curated reference sets need no redundant normalised-name column.
                candidates = {
                    row.id
                    for row in self.session.execute(
                        select(canonical.id, canonical.name, canonical.slug)
                    )
                    if normalised in (normalise_text(row.name), normalise_text(row.slug))
                }
                candidates.update(
                    self.session.scalars(
                        select(owner_column).where(alias.normalised_alias == normalised)
                    )
                )
                return tuple(sorted(candidates))
        except (SQLAlchemyError, ValueError, TypeError):
            raise IdentityPersistenceError("Reference identity lookup failed") from None

    def manufacturer_candidates(self, normalised: str) -> tuple[UUID, ...]:
        return self._named_candidates(
            Manufacturer, ManufacturerAlias, ManufacturerAlias.manufacturer_id, normalised
        )

    def retailer_candidates(self, normalised: str) -> tuple[UUID, ...]:
        return self._named_candidates(
            Retailer, RetailerAlias, RetailerAlias.retailer_id, normalised
        )

    def retailer_group_candidates(self, normalised: str) -> tuple[UUID, ...]:
        return self._named_candidates(
            RetailerGroup, RetailerGroupAlias, RetailerGroupAlias.retailer_group_id, normalised
        )

    def model_candidates(self, normalised: str, manufacturer_id: UUID) -> tuple[UUID, ...]:
        try:
            with self.session.no_autoflush:
                candidates = {
                    row.id
                    for row in self.session.execute(
                        select(Product.id, Product.model_number).where(
                            Product.manufacturer_id == manufacturer_id,
                            Product.model_number.is_not(None),
                        )
                    )
                    # Legacy nullable/blank model numbers are not accepted identifiers.
                    if row.model_number.strip()
                    and normalise_identifier(row.model_number) == normalised
                }
                candidates.update(
                    self.session.scalars(
                        select(ProductModelAlias.product_id)
                        .join(Product, Product.id == ProductModelAlias.product_id)
                        .where(
                            Product.manufacturer_id == manufacturer_id,
                            ProductModelAlias.normalised_alias == normalised,
                        )
                    )
                )
                return tuple(sorted(candidates))
        except (SQLAlchemyError, ValueError, TypeError):
            raise IdentityPersistenceError("Product model lookup failed") from None

    def sku_candidates(
        self, normalised: str, retailer_id: UUID, manufacturer_id: UUID | None = None
    ) -> tuple[UUID, ...]:
        query = select(RetailerProductSku.product_id).where(
            RetailerProductSku.retailer_id == retailer_id,
            RetailerProductSku.normalised_sku == normalised,
        )
        if manufacturer_id is not None:
            query = query.join(Product, Product.id == RetailerProductSku.product_id).where(
                Product.manufacturer_id == manufacturer_id
            )
        try:
            with self.session.no_autoflush:
                return tuple(sorted(set(self.session.scalars(query))))
        except SQLAlchemyError:
            raise IdentityPersistenceError("Retailer SKU lookup failed") from None

    def retailer_group_ids(self, retailer_id: UUID) -> tuple[UUID, ...]:
        try:
            with self.session.no_autoflush:
                return tuple(
                    self.session.scalars(
                        select(RetailerGroupMember.retailer_group_id)
                        .where(RetailerGroupMember.retailer_id == retailer_id)
                        .order_by(RetailerGroupMember.retailer_group_id)
                    )
                )
        except SQLAlchemyError:
            raise IdentityPersistenceError("Retailer group membership lookup failed") from None
