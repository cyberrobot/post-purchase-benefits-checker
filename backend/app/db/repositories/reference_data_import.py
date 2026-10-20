"""SQLAlchemy reference adapter; caller owns the entire transaction."""

from importlib import import_module

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.application.identity_matching import IdentityResolver
from app.application.reference_data_import import Dataset, PlannedEntity, ReferenceDataConflict
from app.db.models import Manufacturer, Product, Promotion, Retailer, RetailerAlias
from app.db.repositories.identity_matching import SqlAlchemyIdentityRepository
from app.domain.identity_normalisation import MatchStatus, normalise_identifier, normalise_text


class SqlAlchemyReferenceDataRepository:
    def __init__(self, session: Session):
        self.session = session
        self.resolver = IdentityResolver(SqlAlchemyIdentityRepository(session))

    def lock(self) -> None:
        self.session.execute(text("SET LOCAL lock_timeout = '5s'"))
        self.session.execute(text("SET LOCAL statement_timeout = '30s'"))
        self.session.execute(text("SELECT pg_advisory_xact_lock(742098412037112)"))

    def _named(self, kind, name, slug, apply):
        match = (
            self.resolver.resolve_manufacturer(name)
            if kind is Manufacturer
            else self.resolver.resolve_retailer(name)
        )
        if match.status == MatchStatus.AMBIGUOUS:
            raise ReferenceDataConflict(f"Ambiguous {kind.__tablename__} identity")
        slug_match = (
            self.resolver.resolve_manufacturer(slug)
            if kind is Manufacturer
            else self.resolver.resolve_retailer(slug)
        )
        if slug_match.status == MatchStatus.AMBIGUOUS or (
            slug_match.status == MatchStatus.MATCHED
            and (
                match.status != MatchStatus.MATCHED or slug_match.canonical_id != match.canonical_id
            )
        ):
            raise ReferenceDataConflict(f"Conflicting {kind.__tablename__} slug alias")
        by_slug = self.session.scalar(select(kind).where(kind.slug == slug))
        row = self.session.get(kind, match.canonical_id) if match.canonical_id else None
        if by_slug is not None and (row is None or by_slug.id != row.id):
            raise ReferenceDataConflict(f"Conflicting {kind.__tablename__} slug")
        if row is not None:
            if row.name != name or row.slug != slug:
                raise ReferenceDataConflict(f"Conflicting {kind.__tablename__} facts")
        elif apply:
            row = kind(name=name, slug=slug)
            self.session.add(row)
            self.session.flush()
        return row, match.status == MatchStatus.NOT_FOUND

    def catalogue(self, dataset: Dataset, *, apply: bool) -> tuple[PlannedEntity, ...]:
        if self.session.new or self.session.dirty or self.session.deleted:
            raise ReferenceDataConflict("Import requires a session without pending changes")
        self.session.expire_all()
        plan = []
        shops = {}
        for fact in dataset.facts:
            maker, new = self._named(Manufacturer, fact.manufacturer, fact.manufacturer_slug, apply)
            plan.append(
                PlannedEntity("manufacturer", fact.manufacturer_slug, "create" if new else "reuse")
            )
            if fact.retailer_slug not in shops:
                shop, new = self._named(Retailer, fact.retailer, fact.retailer_slug, apply)
                shops[fact.retailer_slug] = shop
                plan.append(
                    PlannedEntity("retailer", fact.retailer_slug, "create" if new else "reuse")
                )
            shop = shops[fact.retailer_slug]
            if fact.retailer_alias:
                match = self.resolver.resolve_retailer(fact.retailer_alias)
                if match.status == MatchStatus.AMBIGUOUS or (
                    match.status == MatchStatus.MATCHED
                    and (shop is None or match.canonical_id != shop.id)
                ):
                    raise ReferenceDataConflict("Conflicting Currys - UK alias owner")
                alias = (
                    self.session.get(RetailerAlias, (shop.id, normalise_text(fact.retailer_alias)))
                    if shop
                    else None
                )
                if alias and alias.alias != fact.retailer_alias:
                    raise ReferenceDataConflict("Conflicting retailer alias display")
                if alias is None and match.status == MatchStatus.MATCHED:
                    raise ReferenceDataConflict("Conflicting retailer alias identity")
                plan.append(
                    PlannedEntity(
                        "retailer_alias", fact.retailer_alias, "reuse" if alias else "create"
                    )
                )
                if apply and alias is None:
                    self.session.add(RetailerAlias(retailer_id=shop.id, alias=fact.retailer_alias))
                    self.session.flush()
            rows = [
                row
                for row in (
                    self.session.scalars(select(Product).where(Product.manufacturer_id == maker.id))
                    if maker
                    else ()
                )
                if row.model_number
                and normalise_identifier(row.model_number) == normalise_identifier(fact.model)
            ]
            if len(rows) > 1:
                raise ReferenceDataConflict("Ambiguous normalized model identity")
            row = rows[0] if rows else None
            if maker:
                match = self.resolver.resolve_product(
                    fact.model,
                    manufacturer_id=maker.id,
                    retailer_id=shop.id if shop else None,
                )
                if match.status == MatchStatus.AMBIGUOUS or (
                    match.status == MatchStatus.MATCHED
                    and (row is None or match.canonical_id != row.id)
                ):
                    raise ReferenceDataConflict("Conflicting product model alias")
                slug_row = self.session.scalar(
                    select(Product).where(
                        Product.manufacturer_id == maker.id, Product.slug == fact.product_slug
                    )
                )
                if slug_row is not None and (row is None or row.id != slug_row.id):
                    raise ReferenceDataConflict("Conflicting product slug")
            if row and (
                maker is None
                or row.manufacturer_id != maker.id
                or row.name != fact.product
                or row.slug != fact.product_slug
                or row.model_number != fact.model
            ):
                raise ReferenceDataConflict("Conflicting product facts or manufacturer ownership")
            plan.append(PlannedEntity("product", fact.model, "reuse" if row else "create"))
            if apply and row is None:
                self.session.add(
                    Product(
                        manufacturer_id=maker.id,
                        name=fact.product,
                        slug=fact.product_slug,
                        model_number=fact.model,
                    )
                )
                self.session.flush()
        return tuple(plan)

    def preview_promotions(self, dataset: Dataset) -> tuple[PlannedEntity, ...]:
        """Reuse canonical constructors and graph comparisons without persisting objects."""
        return self._promotions(dataset, preview=True)

    def stage(self, dataset: Dataset) -> tuple[int, int]:
        plan = self._promotions(dataset, preview=False)
        return (sum(e.action == "create" for e in plan), sum(e.action == "reuse" for e in plan))

    def _promotions(self, dataset: Dataset, *, preview: bool) -> tuple[PlannedEntity, ...]:
        self.session.expire_all()
        plan = []
        for fact in dataset.facts:
            constructor = import_module(f"app.db.reference.{fact.manufacturer_slug}")
            maker = self.resolver.resolve_manufacturer(fact.manufacturer)
            try:
                manifest = constructor.reference_manifest()
                existing = self.session.scalar(
                    select(Promotion.id).where(
                        Promotion.manufacturer_id == maker.canonical_id,
                        Promotion.slug == manifest["promotion_slug"],
                    )
                )
                constructor.construct_reference(self.session, preview=preview)
            except ValueError:
                raise ReferenceDataConflict(
                    f"{fact.manufacturer}: reviewed graph or candidate evidence conflict"
                ) from None
            plan.append(
                PlannedEntity(
                    "promotion", manifest["promotion_slug"], "reuse" if existing else "create"
                )
            )
        return tuple(plan)
