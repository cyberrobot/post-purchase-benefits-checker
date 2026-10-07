from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from threading import Barrier
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import MetaData, Table, delete, event, func, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.application.identity_matching import IdentityPersistenceError, IdentityResolver
from app.db.base import Base
from app.db.models import (
    Benefit,
    Manufacturer,
    ManufacturerAlias,
    Product,
    ProductModelAlias,
    Promotion,
    PromotionSource,
    PromotionVariant,
    PromotionVariantProduct,
    Requirement,
    Retailer,
    RetailerAlias,
    RetailerGroup,
    RetailerGroupAlias,
    RetailerGroupMember,
    RetailerProductSku,
    Source,
)
from app.db.repositories.identity_matching import SqlAlchemyIdentityRepository
from app.domain.identity_normalisation import MatchStatus

pytestmark = pytest.mark.integration


@pytest.fixture
def references(db_session):
    manufacturers = [Manufacturer(name=f"Maker {i}", slug=f"maker-{i}") for i in range(2)]
    retailers = [Retailer(name=f"Shop {i}", slug=f"shop-{i}") for i in range(2)]
    groups = [RetailerGroup(name=f"Group {i}", slug=f"group-{i}") for i in range(2)]
    products = [
        Product(manufacturer=manufacturers[0], name="Product A", slug="a", model_number="AB-123"),
        Product(manufacturer=manufacturers[0], name="Product B", slug="b", model_number="BB-123"),
        Product(manufacturer=manufacturers[1], name="Product C", slug="c", model_number="AB-123"),
    ]
    db_session.add_all(manufacturers + retailers + groups + products)
    db_session.flush()
    return manufacturers, retailers, groups, products


@pytest.fixture
def resolver(db_session):
    return IdentityResolver(SqlAlchemyIdentityRepository(db_session))


@pytest.mark.parametrize(
    "kind,model,owner,operation",
    [
        (0, ManufacturerAlias, "manufacturer_id", "resolve_manufacturer"),
        (1, RetailerAlias, "retailer_id", "resolve_retailer"),
        (2, RetailerGroupAlias, "retailer_group_id", "resolve_retailer_group"),
    ],
)
def test_canonical_and_alias_identity(
    db_session, references, resolver, kind, model, owner, operation
):
    canonical = references[kind][0]
    db_session.add(model(**{owner: canonical.id, "alias": " Ｃｕｒａｔｅｄ   Name "}))
    db_session.flush()
    resolve = getattr(resolver, operation)
    for value in (canonical.name.upper(), canonical.slug.upper(), "curated name"):
        result = resolve(value)
        assert result.status == MatchStatus.MATCHED
        assert result.canonical_id == canonical.id
        assert result.candidate_ids == (canonical.id,)
    assert resolve("missing").status == MatchStatus.NOT_FOUND
    assert db_session.scalar(select(func.count()).select_from(model)) == 1
    # Canonical + alias references to the same ID must collapse.
    db_session.add(model(**{owner: canonical.id, "alias": canonical.name}))
    db_session.flush()
    assert resolve(canonical.name).canonical_id == canonical.id


@pytest.mark.parametrize(
    "kind,model,owner,operation",
    [
        (0, ManufacturerAlias, "manufacturer_id", "resolve_manufacturer"),
        (1, RetailerAlias, "retailer_id", "resolve_retailer"),
        (2, RetailerGroupAlias, "retailer_group_id", "resolve_retailer_group"),
    ],
)
@pytest.mark.parametrize("collision", ["alias", "canonical", "name_alias", "slug_alias"])
def test_named_ambiguity(
    db_session, references, resolver, kind, model, owner, operation, collision
):
    first, second = references[kind]
    match collision:
        case "alias":
            value = "shared alias"
            db_session.add_all(
                [
                    model(**{owner: first.id, "alias": value}),
                    model(**{owner: second.id, "alias": " ＳＨＡＲＥＤ   ALIAS "}),
                ]
            )
        case "canonical":
            second.name = f" {first.name.upper()} "
            value = first.name
        case "name_alias":
            value = first.name
            db_session.add(model(**{owner: second.id, "alias": value}))
        case "slug_alias":
            value = first.slug
            db_session.add(model(**{owner: second.id, "alias": value}))
    db_session.flush()
    result = getattr(resolver, operation)(value)
    assert result.status == MatchStatus.AMBIGUOUS
    assert result.canonical_id is None
    assert result.candidate_ids == tuple(sorted([first.id, second.id]))


def test_model_scope_and_aliases(db_session, references, resolver):
    manufacturers, _, _, products = references
    a, b, c = products
    assert (
        resolver.resolve_model(" A B-１２３ ", manufacturer_id=manufacturers[0].id).canonical_id
        == a.id
    )
    assert (
        resolver.resolve_model("AB-123", manufacturer_id=manufacturers[1].id).canonical_id == c.id
    )
    assert (
        resolver.resolve_model("AB123", manufacturer_id=manufacturers[0].id).status
        == MatchStatus.NOT_FOUND
    )
    db_session.add(ProductModelAlias(product_id=a.id, alias="AB123"))
    db_session.flush()
    assert resolver.resolve_model("AB123", manufacturer_id=manufacturers[0].id).canonical_id == a.id
    db_session.add(ProductModelAlias(product_id=b.id, alias=" A B123 "))
    db_session.flush()
    ambiguous = resolver.resolve_model("AB123", manufacturer_id=manufacturers[0].id)
    assert ambiguous.status == MatchStatus.AMBIGUOUS
    assert ambiguous.candidate_ids == tuple(sorted([a.id, b.id]))
    assert db_session.scalar(select(func.count()).select_from(Product)) == 3
    assert a.model_number == "AB-123"
    assert (
        resolver.resolve_model("missing", manufacturer_id=manufacturers[0].id).status
        == MatchStatus.NOT_FOUND
    )
    assert resolver.resolve_model("AB-123", manufacturer_id=uuid4()).status == MatchStatus.NOT_FOUND


def test_same_manufacturer_model_collision(db_session, references, resolver):
    manufacturers, _, _, products = references
    products[1].model_number = " a b-123 "
    db_session.flush()
    result = resolver.resolve_model("AB-123", manufacturer_id=manufacturers[0].id)
    assert result.status == MatchStatus.AMBIGUOUS
    assert result.candidate_ids == tuple(sorted(p.id for p in products[:2]))


def test_optional_and_legacy_blank_models(db_session, references, resolver):
    manufacturers, _, _, products = references
    products[0].model_number = None
    products[1].model_number = " \t"
    db_session.flush()
    assert (
        resolver.resolve_model("AB-123", manufacturer_id=manufacturers[0].id).status
        == MatchStatus.NOT_FOUND
    )


def test_scoped_skus_and_manufacturer_filter(db_session, references, resolver):
    manufacturers, retailers, _, products = references
    a, b, c = products
    db_session.add_all(
        [
            RetailerProductSku(retailer_id=retailers[0].id, product_id=a.id, sku=" １２３ "),
            RetailerProductSku(retailer_id=retailers[1].id, product_id=c.id, sku="123"),
        ]
    )
    db_session.flush()
    assert resolver.resolve_sku("123", retailer_id=retailers[0].id).canonical_id == a.id
    assert resolver.resolve_sku("123", retailer_id=retailers[1].id).canonical_id == c.id
    assert resolver.resolve_sku("123", retailer_id=uuid4()).status == MatchStatus.NOT_FOUND
    assert (
        resolver.resolve_sku("missing", retailer_id=retailers[0].id).status == MatchStatus.NOT_FOUND
    )
    assert (
        resolver.resolve_sku(
            "123", retailer_id=retailers[1].id, manufacturer_id=manufacturers[0].id
        ).status
        == MatchStatus.NOT_FOUND
    )
    assert (
        resolver.resolve_product(
            "123", retailer_id=retailers[1].id, manufacturer_id=manufacturers[0].id
        ).status
        == MatchStatus.NOT_FOUND
    )
    # A retailer/SKU may legitimately be ambiguous across products.
    db_session.add(RetailerProductSku(retailer_id=retailers[0].id, product_id=b.id, sku="1 23"))
    db_session.flush()
    result = resolver.resolve_sku("123", retailer_id=retailers[0].id)
    assert result.status == MatchStatus.AMBIGUOUS
    assert result.candidate_ids == tuple(sorted([a.id, b.id]))


@pytest.mark.parametrize("conflict", [False, True])
def test_combined_model_sku(db_session, references, resolver, conflict):
    manufacturers, retailers, _, products = references
    sku_product = products[1] if conflict else products[0]
    db_session.add(
        RetailerProductSku(retailer_id=retailers[0].id, product_id=sku_product.id, sku="AB-123")
    )
    db_session.flush()
    result = resolver.resolve_product(
        "AB-123", manufacturer_id=manufacturers[0].id, retailer_id=retailers[0].id
    )
    assert result.status == (MatchStatus.AMBIGUOUS if conflict else MatchStatus.MATCHED)
    assert result.candidate_ids == tuple(sorted({products[0].id, sku_product.id}))


def test_other_manufacturer_sku_does_not_conflict_with_model(db_session, references, resolver):
    manufacturers, retailers, _, products = references
    db_session.add(
        RetailerProductSku(retailer_id=retailers[0].id, product_id=products[2].id, sku="AB-123")
    )
    db_session.flush()
    assert (
        resolver.resolve_product(
            "AB-123", manufacturer_id=manufacturers[0].id, retailer_id=retailers[0].id
        ).canonical_id
        == products[0].id
    )


def test_current_group_memberships(db_session, references, resolver):
    _, retailers, groups, _ = references
    assert resolver.retailer_group_ids(retailers[0].id) == ()
    assert isinstance(groups[0].id, UUID)
    assert groups[0].created_at.tzinfo is not None
    assert groups[0].updated_at.tzinfo is not None
    for i, group in enumerate(groups):
        db_session.add(RetailerGroupMember(retailer_group_id=group.id, retailer_id=retailers[0].id))
        db_session.flush()
        assert resolver.retailer_group_ids(retailers[0].id) == tuple(
            sorted(g.id for g in groups[: i + 1])
        )
    assert resolver.retailer_group_ids(retailers[1].id) == ()
    assert resolver.retailer_group_ids(uuid4()) == ()
    assert db_session.scalar(select(func.count()).select_from(Promotion)) == 0
    old = datetime(2000, 1, 1, tzinfo=UTC)
    groups[0].updated_at = old
    db_session.flush()
    groups[0].name = "Updated group"
    db_session.flush()
    assert groups[0].updated_at > old


@pytest.mark.parametrize(
    "kind", ["manufacturer", "retailer", "model", "group", "sku", "membership"]
)
def test_duplicate_reference_retry_rejected_and_transaction_recovers(db_session, references, kind):
    manufacturers, retailers, groups, products = references
    match kind:
        case "manufacturer":
            model, values = (
                ManufacturerAlias,
                {"manufacturer_id": manufacturers[0].id, "alias": " Shared "},
            )
        case "retailer":
            model, values = RetailerAlias, {"retailer_id": retailers[0].id, "alias": " Shared "}
        case "model":
            model, values = ProductModelAlias, {"product_id": products[0].id, "alias": " Shared "}
        case "group":
            model, values = (
                RetailerGroupAlias,
                {"retailer_group_id": groups[0].id, "alias": " Shared "},
            )
        case "sku":
            model, values = (
                RetailerProductSku,
                {"retailer_id": retailers[0].id, "product_id": products[0].id, "sku": " Shared "},
            )
        case "membership":
            model, values = (
                RetailerGroupMember,
                {"retailer_group_id": groups[0].id, "retailer_id": retailers[0].id},
            )
    db_session.add(model(**values))
    db_session.flush()
    if "alias" in values:
        values["alias"] = "ＳＨＡＲＥＤ"
    if "sku" in values:
        values["sku"] = "Ｓ Ｈ Ａ Ｒ Ｅ Ｄ"
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.add(model(**values))
        db_session.flush()
    assert error.value.orig.sqlstate == "23505"
    assert db_session.scalar(select(func.count()).select_from(model)) == 1
    assert db_session.scalar(select(func.count()).select_from(Product)) == 3


@pytest.mark.parametrize(
    "case,values",
    [
        ("empty_name", {"name": "   ", "slug": "new"}),
        ("invalid_slug", {"name": "Valid", "slug": "Not Valid"}),
        ("duplicate_slug", {"name": "Valid", "slug": "group-0"}),
    ],
)
def test_group_integrity(db_session, references, case, values):
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.add(RetailerGroup(**values))
        db_session.flush()


@pytest.mark.parametrize(
    "model,owner,kind",
    [
        (ManufacturerAlias, "manufacturer_id", 0),
        (RetailerAlias, "retailer_id", 1),
        (ProductModelAlias, "product_id", 3),
        (RetailerGroupAlias, "retailer_group_id", 2),
    ],
)
def test_alias_write_normalisation_and_update(db_session, references, model, owner, kind):
    record = model(**{owner: references[kind][0].id, "alias": "Ａ Ｂ", "normalised_alias": "wrong"})
    db_session.add(record)
    db_session.flush()
    assert record.normalised_alias == ("ab" if model is ProductModelAlias else "a b")
    record.alias = "Ｎｅｗ  Name"
    record.normalised_alias = "tampered"
    db_session.flush()
    db_session.expire_all()
    stored = db_session.scalar(select(model))
    assert stored.normalised_alias == ("newname" if model is ProductModelAlias else "new name")


@pytest.mark.parametrize("kind", ["manufacturer", "retailer", "model", "group", "sku"])
@pytest.mark.parametrize("value", ["", " \t", "x" * 256, "ß" * 255])
def test_invalid_reference_orm_writes(db_session, references, kind, value):
    manufacturers, retailers, groups, products = references
    constructors = {
        "manufacturer": lambda: ManufacturerAlias(manufacturer_id=manufacturers[0].id, alias=value),
        "retailer": lambda: RetailerAlias(retailer_id=retailers[0].id, alias=value),
        "model": lambda: ProductModelAlias(product_id=products[0].id, alias=value),
        "group": lambda: RetailerGroupAlias(retailer_group_id=groups[0].id, alias=value),
        "sku": lambda: RetailerProductSku(
            retailer_id=retailers[0].id, product_id=products[0].id, sku=value
        ),
    }
    with pytest.raises(ValueError), db_session.begin_nested():
        db_session.add(constructors[kind]())
        db_session.flush()


@pytest.mark.parametrize(
    "model,owner,kind,raw,key",
    [
        (ManufacturerAlias, "manufacturer_id", 0, "alias", "normalised_alias"),
        (RetailerAlias, "retailer_id", 1, "alias", "normalised_alias"),
        (ProductModelAlias, "product_id", 3, "alias", "normalised_alias"),
        (RetailerGroupAlias, "retailer_group_id", 2, "alias", "normalised_alias"),
        (RetailerProductSku, "product_id", 3, "sku", "normalised_sku"),
    ],
)
@pytest.mark.parametrize(
    "bad_field,bad_value", [("raw", " "), ("key", " "), ("raw", "x" * 256), ("key", "x" * 256)]
)
def test_database_bounds_without_orm_hooks(
    db_session, references, model, owner, kind, raw, key, bad_field, bad_value
):
    values = {owner: references[kind][0].id, raw: "Valid", key: "valid"}
    if model is RetailerProductSku:
        values["retailer_id"] = references[1][0].id
    values[raw if bad_field == "raw" else key] = bad_value
    with (
        pytest.raises(IntegrityError if len(bad_value) <= 255 else DataError),
        db_session.begin_nested(),
    ):
        db_session.execute(model.__table__.insert().values(**values))


@pytest.mark.parametrize(
    "model,values",
    [
        (ManufacturerAlias, {"manufacturer_id": uuid4(), "alias": "Valid"}),
        (RetailerAlias, {"retailer_id": uuid4(), "alias": "Valid"}),
        (ProductModelAlias, {"product_id": uuid4(), "alias": "Valid"}),
        (RetailerGroupAlias, {"retailer_group_id": uuid4(), "alias": "Valid"}),
        (RetailerProductSku, {"retailer_id": uuid4(), "product_id": uuid4(), "sku": "Valid"}),
        (RetailerGroupMember, {"retailer_group_id": uuid4(), "retailer_id": uuid4()}),
    ],
)
def test_orphan_references_rejected(db_session, model, values):
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.add(model(**values))
        db_session.flush()
    assert error.value.orig.sqlstate == "23503"


@pytest.mark.parametrize("orm_delete", [False, True])
def test_group_delete_cascades_only_associations(db_session, references, resolver, orm_delete):
    _, retailers, groups, _ = references
    group = groups[0]
    db_session.add_all(
        [
            RetailerGroupMember(retailer_group_id=group.id, retailer_id=retailers[0].id),
            RetailerGroupMember(retailer_group_id=groups[1].id, retailer_id=retailers[0].id),
            RetailerGroupAlias(retailer_group_id=group.id, alias="Curated"),
        ]
    )
    db_session.flush()
    assert len(group.members) == 1
    if orm_delete:
        db_session.delete(group)
    else:
        db_session.execute(delete(RetailerGroup).where(RetailerGroup.id == group.id))
    db_session.flush()
    assert db_session.scalar(select(func.count()).select_from(RetailerGroupAlias)) == 0
    assert resolver.retailer_group_ids(retailers[0].id) == (groups[1].id,)
    assert db_session.get(Retailer, retailers[0].id) is not None
    db_session.execute(delete(RetailerGroupMember))
    assert db_session.get(RetailerGroup, groups[1].id) is not None
    assert db_session.get(Retailer, retailers[0].id) is not None


@pytest.mark.parametrize("kind", ["manufacturer", "product", "retailer"])
@pytest.mark.parametrize("orm_delete", [False, True])
def test_owned_aliases_cascade(db_session, kind, orm_delete):
    manufacturer = Manufacturer(name="Maker", slug="maker")
    retailer = Retailer(name="Shop", slug="shop")
    product = Product(manufacturer=manufacturer, name="Product", slug="product")
    db_session.add_all([manufacturer, retailer, product])
    db_session.flush()
    aliases = {
        "manufacturer": (
            manufacturer,
            ManufacturerAlias(manufacturer_id=manufacturer.id, alias="Alias"),
        ),
        "product": (product, ProductModelAlias(product_id=product.id, alias="Alias")),
        "retailer": (retailer, RetailerAlias(retailer_id=retailer.id, alias="Alias")),
    }
    record, alias = aliases[kind]
    db_session.add(alias)
    if kind == "manufacturer":
        # Only otherwise deletable manufacturers may cascade their aliases.
        db_session.delete(product)
    if kind == "retailer":
        group = RetailerGroup(name="Group", slug="group")
        db_session.add(group)
        db_session.flush()
        db_session.add(RetailerGroupMember(retailer_id=retailer.id, retailer_group_id=group.id))
    db_session.flush()
    if orm_delete:
        db_session.delete(record)
    else:
        db_session.execute(delete(type(record)).where(type(record).id == record.id))
    db_session.flush()
    assert db_session.scalar(select(func.count()).select_from(type(alias))) == 0
    if kind == "retailer":
        assert db_session.scalar(select(func.count()).select_from(RetailerGroupMember)) == 0
        assert db_session.get(RetailerGroup, group.id) is not None


@pytest.mark.parametrize("kind", ["retailer", "product"])
@pytest.mark.parametrize("orm_delete", [False, True])
def test_sku_reference_deletion_restricted(db_session, references, kind, orm_delete):
    _, retailers, _, products = references
    record = retailers[0] if kind == "retailer" else products[0]
    db_session.add(
        RetailerProductSku(retailer_id=retailers[0].id, product_id=products[0].id, sku="123")
    )
    db_session.flush()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        if orm_delete:
            db_session.delete(record)
        else:
            db_session.execute(delete(type(record)).where(type(record).id == record.id))
        db_session.flush()
    assert db_session.scalar(select(func.count()).select_from(RetailerProductSku)) == 1


@pytest.mark.parametrize(
    "operation,kwargs",
    [
        ("resolve_manufacturer", {}),
        ("resolve_retailer", {}),
        ("resolve_retailer_group", {}),
        ("resolve_model", {"manufacturer_id": uuid4()}),
        ("resolve_sku", {"retailer_id": uuid4()}),
        ("resolve_product", {"manufacturer_id": uuid4(), "retailer_id": uuid4()}),
    ],
)
def test_database_failures_are_safely_wrapped(db_session, operation, kwargs):
    # A real failed PostgreSQL transaction, not a mocked repository result.
    with db_session.begin_nested() as savepoint:
        with pytest.raises(DataError):
            db_session.execute(text("SELECT 1 / 0"))
        with pytest.raises(IdentityPersistenceError) as error:
            getattr(IdentityResolver(SqlAlchemyIdentityRepository(db_session)), operation)(
                "valid", **kwargs
            )
        assert "SQL" not in str(error.value)
        assert "SELECT" not in str(error.value)
        assert error.value.__cause__ is None
        savepoint.rollback()
    assert db_session.execute(text("SELECT 1")).scalar_one() == 1


def test_no_autoflush_and_matching_has_no_writes(db_session, references, resolver):
    pending = Manufacturer(name="Pending", slug="pending")
    db_session.add(pending)
    statements = []
    connection = db_session.connection()

    def capture(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(connection, "before_cursor_execute", capture)
    try:
        assert resolver.resolve_manufacturer("Pending").status == MatchStatus.NOT_FOUND
        assert resolver.resolve_manufacturer("Maker 0").canonical_id == references[0][0].id
        assert resolver.resolve_retailer("missing").status == MatchStatus.NOT_FOUND
        assert resolver.resolve_retailer_group("missing").status == MatchStatus.NOT_FOUND
        assert (
            resolver.resolve_product(
                "missing", manufacturer_id=references[0][0].id, retailer_id=references[1][0].id
            ).status
            == MatchStatus.NOT_FOUND
        )
        assert resolver.retailer_group_ids(references[1][0].id) == ()
    finally:
        event.remove(connection, "before_cursor_execute", capture)
    assert pending.id is None
    assert statements and set(statements) == {"SELECT"}


def test_upgrade_preserves_existing_graph_and_round_trip(postgres_engine):
    """Isolated transactional schema: start at PR 6 and retain every original table row."""
    schema = f"migration_{uuid4().hex}"
    with postgres_engine.connect() as connection, connection.begin():
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
        config = Config("alembic.ini")
        config.attributes["connection"] = connection
        command.upgrade(config, "0002_core_promotion_schema")
        maker, product, retailer, promotion, variant, source = [uuid4() for _ in range(6)]
        now = datetime(2026, 10, 6, tzinfo=UTC)
        records = [
            (Manufacturer, {"id": maker, "name": "Maker", "slug": "maker"}),
            (
                Product,
                {
                    "id": product,
                    "manufacturer_id": maker,
                    "name": "Product",
                    "slug": "product",
                    "model_number": " AB-123 ",
                },
            ),
            (Retailer, {"id": retailer, "name": "Shop", "slug": "shop"}),
            (
                Promotion,
                {
                    "id": promotion,
                    "manufacturer_id": maker,
                    "name": "Published",
                    "slug": "published",
                    "status": "active",
                    "purchase_start_date": date(2026, 10, 1),
                    "purchase_end_date": date(2026, 10, 31),
                },
            ),
            (
                PromotionVariant,
                {
                    "id": variant,
                    "promotion_id": promotion,
                    "retailer_id": retailer,
                    "code": "default",
                },
            ),
            (PromotionVariantProduct, {"promotion_variant_id": variant, "product_id": product}),
            (
                Benefit,
                {
                    "id": uuid4(),
                    "promotion_variant_id": variant,
                    "benefit_type": "cashback",
                    "name": "Cashback",
                },
            ),
            (
                Requirement,
                {"id": uuid4(), "promotion_variant_id": variant, "requirement_type": "receipt"},
            ),
            (
                Source,
                {
                    "id": source,
                    "url": "https://example.invalid/offer",
                    "source_type": "web_page",
                    "retrieved_at": now,
                    "verified_at": now,
                },
            ),
            (PromotionSource, {"promotion_id": promotion, "source_id": source, "role": "primary"}),
        ]
        # Reflect the historical schema rather than selecting later ORM additions.
        historical_metadata = MetaData()
        historical_tables = {
            model: Table(model.__tablename__, historical_metadata, autoload_with=connection)
            for model, _ in records
        }
        for model, values in records:
            connection.execute(historical_tables[model].insert().values(**values))
        snapshot = {
            model: connection.execute(select(historical_tables[model])).all()
            for model, _ in records
        }
        command.upgrade(config, "0003_identity_normalisation")
        for model, before in snapshot.items():
            assert connection.execute(select(historical_tables[model])).all() == before
        # This historical revision creates only identity tables. Later reward
        # tables are absent here and belong to their own migration tests.
        identity_tables = {
            model.__tablename__
            for model in (
                ManufacturerAlias,
                ProductModelAlias,
                RetailerAlias,
                RetailerProductSku,
                RetailerGroup,
                RetailerGroupAlias,
                RetailerGroupMember,
            )
        }
        for table_name in identity_tables:
            assert (
                connection.scalar(
                    select(func.count()).select_from(Base.metadata.tables[table_name])
                )
                == 0
            )
        command.downgrade(config, "-1")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0002_core_promotion_schema"
        )
        for model, before in snapshot.items():
            assert connection.execute(select(historical_tables[model])).all() == before
        command.upgrade(config, "0003_identity_normalisation")
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0003_identity_normalisation"
        )
        # Resolve canonical rows without a migration backfill into aliases.
        with Session(bind=connection, join_transaction_mode="create_savepoint") as session:
            resolver = IdentityResolver(SqlAlchemyIdentityRepository(session))
            assert resolver.resolve_manufacturer("Maker").canonical_id == maker
            assert resolver.resolve_retailer("Shop").canonical_id == retailer
            assert resolver.resolve_model("AB-123", manufacturer_id=maker).canonical_id == product
        connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.mark.parametrize(
    "kind", ["manufacturer", "retailer", "model", "group", "sku", "membership"]
)
def test_concurrent_duplicate_writes_are_atomic(postgres_engine, migrated_test_database, kind):
    """Independent transactions race on the same business key, without read-then-write checks."""
    maker, product, retailer, group = [uuid4() for _ in range(4)]
    suffix = uuid4().hex
    with Session(postgres_engine) as session, session.begin():
        session.add_all(
            [
                Manufacturer(id=maker, name="Race maker", slug=f"race-{suffix}"),
                Retailer(id=retailer, name="Race shop", slug=f"race-{suffix}"),
                RetailerGroup(id=group, name="Race group", slug=f"race-{suffix}"),
            ]
        )
        session.flush()
        session.add(Product(id=product, manufacturer_id=maker, name="Race product", slug="race"))
    model, values = {
        "manufacturer": (ManufacturerAlias, {"manufacturer_id": maker, "alias": "Same alias"}),
        "retailer": (RetailerAlias, {"retailer_id": retailer, "alias": "Same alias"}),
        "model": (ProductModelAlias, {"product_id": product, "alias": "Same alias"}),
        "group": (RetailerGroupAlias, {"retailer_group_id": group, "alias": "Same alias"}),
        "sku": (
            RetailerProductSku,
            {"retailer_id": retailer, "product_id": product, "sku": "Same SKU"},
        ),
        "membership": (RetailerGroupMember, {"retailer_group_id": group, "retailer_id": retailer}),
    }[kind]
    barrier = Barrier(2)

    def write_once():
        with Session(postgres_engine) as session, session.begin():
            session.execute(text("SET LOCAL statement_timeout = '5s'"))
            barrier.wait(timeout=5)
            try:
                with session.begin_nested():
                    session.add(model(**values))
                    session.flush()
                return "inserted"
            except IntegrityError as error:
                assert error.orig.sqlstate == "23505"
                assert session.execute(text("SELECT 1")).scalar_one() == 1
                return "duplicate"

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: write_once(), range(2)))
        assert sorted(results) == ["duplicate", "inserted"]
        with Session(postgres_engine) as session:
            # This test creates only one row for its isolated canonical owner.
            owner_field = next(k for k in values if k.endswith("_id"))
            count = session.scalar(
                select(func.count())
                .select_from(model)
                .where(getattr(model, owner_field) == values[owner_field])
            )
            assert count == 1
    finally:
        with Session(postgres_engine) as session, session.begin():
            session.execute(
                delete(RetailerProductSku).where(RetailerProductSku.product_id == product)
            )
            session.execute(delete(Product).where(Product.id == product))
            session.execute(delete(Manufacturer).where(Manufacturer.id == maker))
            session.execute(delete(Retailer).where(Retailer.id == retailer))
            session.execute(delete(RetailerGroup).where(RetailerGroup.id == group))


@pytest.mark.parametrize(
    "model,field,values",
    [
        (RetailerProductSku, "retailer_id", {"product_id": (3, 0), "sku": "Valid"}),
        (RetailerProductSku, "product_id", {"retailer_id": (1, 0), "sku": "Valid"}),
        (RetailerGroupMember, "retailer_id", {"retailer_group_id": (2, 0)}),
        (RetailerGroupMember, "retailer_group_id", {"retailer_id": (1, 0)}),
    ],
)
def test_each_association_foreign_key_is_enforced(db_session, references, model, field, values):
    values = {
        key: references[value[0]][value[1]].id if isinstance(value, tuple) else value
        for key, value in values.items()
    }
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.add(model(**values, **{field: uuid4()}))
        db_session.flush()
    assert error.value.orig.sqlstate == "23503"


def test_sku_update_rekeys_mapping(db_session, references, resolver):
    _, retailers, _, products = references
    mapping = RetailerProductSku(retailer_id=retailers[0].id, product_id=products[0].id, sku="OLD")
    db_session.add(mapping)
    db_session.flush()
    mapping.sku = " Ｎ Ｅ Ｗ "
    mapping.normalised_sku = "wrong"
    db_session.flush()
    assert resolver.resolve_sku("NEW", retailer_id=retailers[0].id).canonical_id == products[0].id
    assert resolver.resolve_sku("OLD", retailer_id=retailers[0].id).status == MatchStatus.NOT_FOUND
    assert resolver.resolve_sku("NE-W", retailer_id=retailers[0].id).status == MatchStatus.NOT_FOUND


def test_membership_query_failure_remains_infrastructure_failure(db_session, resolver):
    with db_session.begin_nested() as savepoint:
        with pytest.raises(DataError):
            db_session.execute(text("SELECT 1 / 0"))
        with pytest.raises(IdentityPersistenceError):
            resolver.retailer_group_ids(uuid4())
        savepoint.rollback()


def test_invalid_persisted_canonical_value_is_not_not_found(db_session, references, resolver):
    references[0][0].name = "ß" * 255
    db_session.flush()
    with pytest.raises(IdentityPersistenceError):
        resolver.resolve_manufacturer("missing")


def test_identifier_content_is_data(db_session, references, resolver):
    value = "'; DROP TABLE products; --"
    assert (
        resolver.resolve_product(
            value, manufacturer_id=references[0][0].id, retailer_id=references[1][0].id
        ).status
        == MatchStatus.NOT_FOUND
    )
    assert resolver.resolve_manufacturer(value).status == MatchStatus.NOT_FOUND
    assert db_session.scalar(select(func.count()).select_from(Product)) == 3
