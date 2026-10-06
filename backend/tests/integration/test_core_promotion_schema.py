from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    Benefit,
    Manufacturer,
    Product,
    Promotion,
    PromotionSource,
    PromotionVariant,
    PromotionVariantProduct,
    Requirement,
    Retailer,
    Source,
)

pytestmark = pytest.mark.integration
NOW = datetime(2026, 10, 6, tzinfo=UTC)


@pytest.fixture
def graph(db_session: Session) -> Promotion:
    manufacturer = Manufacturer(name="Example", slug="example")
    retailer = Retailer(name="Shop", slug="shop")
    products = [
        Product(
            manufacturer=manufacturer,
            name=f"Product {i}",
            slug=f"product-{i}",
            model_number="shared",
        )
        for i in range(2)
    ]
    promotion = Promotion(
        manufacturer=manufacturer,
        name="Campaign",
        slug="campaign",
        status="active",
        purchase_start_date=date(2026, 10, 1),
        purchase_end_date=date(2026, 10, 1),
    )
    for i in range(3):
        variant = PromotionVariant(
            promotion=promotion, retailer=retailer if i < 2 else None, code=f"variant-{i}"
        )
        variant.product_links = [PromotionVariantProduct(product=p) for p in products]
        variant.benefits = [
            Benefit(benefit_type=t, name=t) for t in ("cashback", "free_gift", "extended_warranty")
        ]
        variant.requirements = [
            Requirement(requirement_type=t)
            for t in ("receipt", "serial_number", "registration", "invoice", "barcode", "imei")
        ]
    promotion.source_links = [
        PromotionSource(
            role=role,
            source=Source(
                url="https://example.invalid/promotion",
                source_type="web_page",
                retrieved_at=NOW,
                verified_at=NOW,
            ),
        )
        for role in ("primary", "terms", "claim", "supporting")
    ]
    db_session.add(promotion)
    db_session.flush()
    return promotion


def test_complete_graph_and_metadata(db_session: Session, graph: Promotion) -> None:
    identity = graph.id
    db_session.expire_all()
    promotion = db_session.get(Promotion, identity)
    assert promotion is not None
    assert isinstance(promotion.id, UUID)
    assert promotion.created_at.tzinfo is not None
    assert promotion.updated_at.tzinfo is not None
    assert len(promotion.manufacturer.products) == 2
    assert len(promotion.variants) == 3
    assert sum(v.retailer is None for v in promotion.variants) == 1
    for variant in promotion.variants:
        assert len(variant.product_links) == 2
        assert variant.product_links[0].product.manufacturer == promotion.manufacturer
        assert len(variant.benefits) == 3
        assert len(variant.requirements) == 6
    assert {link.role for link in promotion.source_links} == {
        "primary",
        "terms",
        "claim",
        "supporting",
    }
    assert len({link.source.id for link in promotion.source_links}) == 4
    differences = compare_metadata(
        MigrationContext.configure(db_session.connection()), Base.metadata
    )
    assert [
        d
        for d in differences
        if not (d[0] == "remove_table" and d[1].name == "test_session_isolation_probe")
    ] == []
    previous = promotion.updated_at
    promotion.name = "Updated campaign"
    db_session.flush()
    assert promotion.updated_at >= previous


@pytest.mark.parametrize(
    "status", ["discovered", "extracted", "review", "active", "expired", "archived"]
)
def test_lifecycle_can_retain_incomplete_records(db_session: Session, status: str) -> None:
    promotion = Promotion(
        manufacturer=Manufacturer(name="Example", slug="example"),
        name="Candidate",
        slug="candidate",
        status=status,
    )
    db_session.add(promotion)
    db_session.flush()
    assert promotion.status == status
    assert promotion.variants == []
    assert promotion.purchase_start_date is None


@pytest.mark.parametrize(
    "case",
    [
        "manufacturer_slug",
        "retailer_slug",
        "product_slug",
        "promotion_slug",
        "variant_code",
        "product_link",
        "source_link",
        "status",
        "benefit",
        "requirement",
        "source_type",
        "role",
        "purchase_dates",
        "verification_dates",
        "empty_name",
        "slug",
    ],
)
def test_invalid_data_rejected(db_session: Session, graph: Promotion, case: str) -> None:
    variant = graph.variants[0]
    product = variant.product_links[0].product
    source = graph.source_links[0].source
    with pytest.raises(IntegrityError), db_session.begin_nested():
        match case:
            case "manufacturer_slug":
                db_session.add(Manufacturer(name="Duplicate", slug=graph.manufacturer.slug))
            case "retailer_slug":
                db_session.add(Retailer(name="Duplicate", slug=variant.retailer.slug))
            case "product_slug":
                db_session.add(
                    Product(
                        manufacturer_id=product.manufacturer_id, name="Duplicate", slug=product.slug
                    )
                )
            case "promotion_slug":
                db_session.add(
                    Promotion(
                        manufacturer_id=graph.manufacturer_id,
                        name="Duplicate",
                        slug=graph.slug,
                        status="review",
                    )
                )
            case "variant_code":
                db_session.add(PromotionVariant(promotion_id=graph.id, code=variant.code))
            case "product_link":
                db_session.execute(
                    PromotionVariantProduct.__table__.insert().values(
                        promotion_variant_id=variant.id, product_id=product.id
                    )
                )
            case "source_link":
                db_session.execute(
                    PromotionSource.__table__.insert().values(
                        promotion_id=graph.id, source_id=source.id, role="terms"
                    )
                )
            case "status":
                graph.status = "published"
            case "benefit":
                variant.benefits[0].benefit_type = "unsupported"
            case "requirement":
                variant.requirements[0].requirement_type = "unsupported"
            case "source_type":
                source.source_type = "unsupported"
            case "role":
                graph.source_links[0].role = "unsupported"
            case "purchase_dates":
                graph.purchase_end_date = date(2026, 9, 30)
            case "verification_dates":
                source.verified_at = NOW - timedelta(seconds=1)
            case "empty_name":
                product.name = "   "
            case "slug":
                graph.manufacturer.slug = "Not Normalized"
        db_session.flush()


@pytest.mark.parametrize(
    "model,field",
    [
        (Product, "manufacturer_id"),
        (Promotion, "manufacturer_id"),
        (PromotionVariant, "promotion_id"),
        (PromotionVariant, "retailer_id"),
        (Benefit, "promotion_variant_id"),
        (Requirement, "promotion_variant_id"),
        (PromotionVariantProduct, "product_id"),
        (PromotionVariantProduct, "promotion_variant_id"),
        (PromotionSource, "promotion_id"),
        (PromotionSource, "source_id"),
    ],
)
def test_orphans_rejected(db_session: Session, graph: Promotion, model, field: str) -> None:
    record = db_session.scalars(select(model)).first()
    with pytest.raises(IntegrityError), db_session.begin_nested():
        setattr(record, field, uuid4())
        db_session.flush()


@pytest.mark.parametrize("reference", ["manufacturer", "product", "retailer", "source"])
@pytest.mark.parametrize("orm_delete", [True, False])
def test_reference_deletion_restricted(
    db_session: Session, graph: Promotion, reference: str, orm_delete: bool
) -> None:
    variant = graph.variants[0]
    record = {
        "manufacturer": graph.manufacturer,
        "product": variant.product_links[0].product,
        "retailer": variant.retailer,
        "source": graph.source_links[0].source,
    }[reference]
    # Load reverse relationships to ensure ORM deletion cannot silently unlink references.
    for rel in record.__mapper__.relationships:
        getattr(record, rel.key)
    with pytest.raises(IntegrityError), db_session.begin_nested():
        if orm_delete:
            db_session.delete(record)
        else:
            db_session.execute(delete(type(record)).where(type(record).id == record.id))
        db_session.flush()


@pytest.mark.parametrize("orm_delete", [True, False])
@pytest.mark.parametrize("scope", ["promotion", "variant"])
def test_owned_graph_cascades_preserve_references(
    db_session: Session, graph: Promotion, orm_delete: bool, scope: str
) -> None:
    record = graph if scope == "promotion" else graph.variants[0]
    if orm_delete:
        db_session.delete(record)
    else:
        db_session.execute(delete(type(record)).where(type(record).id == record.id))
    db_session.flush()
    remaining = 0 if scope == "promotion" else 2
    for model, expected in [
        (PromotionVariant, remaining),
        (Benefit, remaining * 3),
        (Requirement, remaining * 6),
        (PromotionVariantProduct, remaining * 2),
        (PromotionSource, 0 if scope == "promotion" else 4),
        (Manufacturer, 1),
        (Product, 2),
        (Retailer, 1),
        (Source, 4),
    ]:
        assert db_session.scalar(select(func.count()).select_from(model)) == expected


def test_scoped_identifiers_can_repeat(db_session: Session, graph: Promotion) -> None:
    other = Manufacturer(name="Other", slug="other")
    db_session.add_all(
        [
            Product(manufacturer=other, name="Other product", slug="product-0"),
            Promotion(
                manufacturer=other, name="Other campaign", slug="campaign", status="discovered"
            ),
        ]
    )
    db_session.flush()
