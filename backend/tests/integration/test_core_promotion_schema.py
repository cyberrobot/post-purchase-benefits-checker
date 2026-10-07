import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import (
    Benefit,
    BenefitProductRewardValue,
    BenefitReward,
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
from app.domain.benefits import Benefit as DomainBenefit
from app.domain.benefits import BenefitType
from app.domain.requirements import Requirement as DomainRequirement
from app.domain.requirements import RequirementType
from app.domain.rewards import (
    FixedAmountReward,
    PercentageReward,
    ProductRewardValue,
    ProductSpecificReward,
    RewardType,
    calculate_reward,
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
        variant.requirements = [Requirement(requirement_type=t) for t in RequirementType]
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
        assert all(
            link.product.manufacturer_id == promotion.manufacturer_id
            for link in variant.product_links
        )
        assert len(variant.benefits) == 3
        assert {row.requirement_type for row in variant.requirements} == set(RequirementType)
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
    previous = datetime(2000, 1, 1, tzinfo=UTC)
    promotion.updated_at = previous
    db_session.flush()
    promotion.name = "Updated campaign"
    db_session.flush()
    assert promotion.updated_at > previous


@pytest.mark.parametrize("benefit_type", list(BenefitType))
def test_domain_benefit_round_trip(
    db_session: Session, graph: Promotion, benefit_type: BenefitType
) -> None:
    benefit = DomainBenefit(benefit_type, "Benefit display name", "Benefit description")
    variant_id = graph.variants[0].id
    row = Benefit(
        promotion_variant_id=variant_id,
        benefit_type=benefit.benefit_type.value,
        name=benefit.name,
        description=benefit.description,
    )
    db_session.add(row)
    db_session.flush()
    identity = row.id
    db_session.expire_all()
    stored = db_session.get(Benefit, identity)
    assert stored is not None
    assert stored.promotion_variant_id == variant_id
    assert stored.benefit_type == benefit_type.value
    assert (
        DomainBenefit(BenefitType(stored.benefit_type), stored.name, stored.description) == benefit
    )


@pytest.mark.parametrize("value", ["rebate", "gift", "warranty", "CASHBACK", "other", ""])
def test_unsupported_benefit_classification_rejected(
    db_session: Session, graph: Promotion, value: str
) -> None:
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.add(
            Benefit(promotion_variant_id=graph.variants[0].id, benefit_type=value, name="Benefit")
        )
        db_session.flush()
    assert error.value.orig.diag.constraint_name == "ck_benefits_type"


@pytest.mark.parametrize("requirement_type", list(RequirementType))
@pytest.mark.parametrize("description", [None, "Provide the original evidence."])
def test_domain_requirement_round_trip(
    db_session: Session,
    graph: Promotion,
    requirement_type: RequirementType,
    description: str | None,
) -> None:
    requirement = DomainRequirement(requirement_type, description)
    variant_id = graph.variants[0].id
    # The graph already has this classification: separate instructions may repeat it.
    row = Requirement(
        promotion_variant_id=variant_id,
        requirement_type=requirement.requirement_type.value,
        description=requirement.description,
    )
    db_session.add(row)
    db_session.flush()
    identity = row.id
    db_session.expire_all()
    stored = db_session.get(Requirement, identity)
    assert stored is not None
    assert stored.promotion_variant_id == variant_id
    assert stored.requirement_type == requirement_type.value
    assert DomainRequirement(stored.requirement_type, stored.description) == requirement
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(Requirement)
            .where(
                Requirement.promotion_variant_id == variant_id,
                Requirement.requirement_type == requirement_type.value,
            )
        )
        == 2
    )


@pytest.mark.parametrize(
    "value", ["proof", "document", "photo", "installer", "warranty_card", "other", "RECEIPT", ""]
)
def test_unsupported_requirement_classification_rejected(
    db_session: Session, graph: Promotion, value: str
) -> None:
    before = db_session.scalar(select(func.count()).select_from(Requirement))
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.add(
            Requirement(promotion_variant_id=graph.variants[0].id, requirement_type=value)
        )
        db_session.flush()
    assert error.value.orig.diag.constraint_name == "ck_requirements_type"
    assert db_session.scalar(select(func.count()).select_from(Requirement)) == before


@pytest.mark.parametrize("status", ["discovered", "extracted", "review"])
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


@pytest.mark.parametrize("status", ["active", "expired", "archived"])
def test_published_and_historical_status_values(
    db_session: Session, graph: Promotion, status: str
) -> None:
    graph.status = status
    db_session.flush()
    db_session.refresh(graph)
    assert graph.status == status


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
        (Requirement, remaining * len(RequirementType)),
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


@pytest.mark.parametrize("reward_type", list(RewardType))
def test_reward_round_trip(db_session: Session, graph: Promotion, reward_type: RewardType) -> None:
    benefit = graph.variants[0].benefits[0]
    products = [link.product for link in graph.variants[0].product_links]
    assert benefit.reward is None
    row = BenefitReward(reward_type=reward_type.value)
    if reward_type is RewardType.FIXED_AMOUNT:
        definition = FixedAmountReward(Decimal("123456789012345678901234567890.12"))
        row.fixed_amount = definition.amount
    elif reward_type is RewardType.PERCENTAGE:
        definition = PercentageReward(Decimal("12.3456"))
        row.percentage = definition.percentage
    else:
        definition = ProductSpecificReward(
            tuple(ProductRewardValue(p.id, Decimal(f"{i + 1}.23")) for i, p in enumerate(products))
        )
        row.product_values = [
            BenefitProductRewardValue(product_id=v.product_id, amount=v.amount)
            for v in definition.values
        ]
    benefit.reward = row
    db_session.flush()
    benefit_id = benefit.id
    product_id = products[0].id
    db_session.expire_all()
    stored = db_session.get(Benefit, benefit_id).reward
    assert stored.reward_type == definition.reward_type.value
    if reward_type is RewardType.FIXED_AMOUNT:
        restored = FixedAmountReward(stored.fixed_amount)
    elif reward_type is RewardType.PERCENTAGE:
        restored = PercentageReward(stored.percentage)
    else:
        restored = ProductSpecificReward(
            tuple(ProductRewardValue(v.product_id, v.amount) for v in stored.product_values)
        )
    assert restored == definition
    assert calculate_reward(restored, product_id=product_id, purchase_price=Decimal("199.99")) == (
        calculate_reward(definition, product_id=product_id, purchase_price=Decimal("199.99"))
    )


@pytest.mark.parametrize("value", ["basket", "conditional", "FIXED_AMOUNT", "other", ""])
def test_reward_discriminator_constraint(db_session: Session, graph: Promotion, value: str) -> None:
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.execute(
            BenefitReward.__table__.insert().values(
                benefit_id=graph.variants[0].benefits[0].id, reward_type=value
            )
        )
    # Unknown types violate both classification and shape. PostgreSQL may report
    # either check first; also prove the dedicated type check matches the domain.
    assert error.value.orig.diag.constraint_name in {
        "ck_benefit_rewards_type",
        "ck_benefit_rewards_shape",
    }
    constraint = next(
        check
        for check in inspect(db_session.connection()).get_check_constraints("benefit_rewards")
        if check["name"] == "ck_benefit_rewards_type"
    )
    assert set(re.findall(r"'([^']+)'", constraint["sqltext"])) == set(RewardType)


@pytest.mark.parametrize(
    "kind,amount,percentage",
    [
        ("fixed_amount", None, None),
        ("fixed_amount", "1", "1"),
        ("fixed_amount", None, "1"),
        ("percentage", None, None),
        ("percentage", "1", "1"),
        ("percentage", "1", None),
        ("product_specific", "1", None),
        ("product_specific", None, "1"),
        ("product_specific", "1", "1"),
    ],
)
def test_reward_shape_constraint(
    db_session: Session, graph: Promotion, kind: str, amount: str | None, percentage: str | None
) -> None:
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.execute(
            BenefitReward.__table__.insert().values(
                benefit_id=graph.variants[0].benefits[0].id,
                reward_type=kind,
                fixed_amount=Decimal(amount) if amount else None,
                percentage=Decimal(percentage) if percentage else None,
            )
        )
    assert error.value.orig.diag.constraint_name == "ck_benefit_rewards_shape"


@pytest.mark.parametrize("target", ["fixed", "percentage", "product"])
@pytest.mark.parametrize(
    "value", ["0", "-1", "NaN", "Infinity", "-Infinity", "12.34567", "1.00000"]
)
def test_reward_numeric_constraints(
    db_session: Session, graph: Promotion, target: str, value: str
) -> None:
    benefit_id = graph.variants[0].benefits[0].id
    if target == "product":
        db_session.execute(
            BenefitReward.__table__.insert().values(
                benefit_id=benefit_id, reward_type="product_specific"
            )
        )
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        if target == "product":
            db_session.execute(
                BenefitProductRewardValue.__table__.insert().values(
                    benefit_id=benefit_id,
                    product_id=graph.variants[0].product_links[0].product_id,
                    amount=Decimal(value),
                )
            )
        else:
            db_session.execute(
                BenefitReward.__table__.insert().values(
                    benefit_id=benefit_id,
                    reward_type="fixed_amount" if target == "fixed" else "percentage",
                    **{"fixed_amount" if target == "fixed" else "percentage": Decimal(value)},
                )
            )
    expected = {
        "fixed": "ck_benefit_rewards_amount",
        "percentage": "ck_benefit_rewards_percentage",
        "product": "ck_benefit_product_reward_values_amount",
    }[target]
    assert error.value.orig.diag.constraint_name == expected
    if target != "product":
        assert db_session.get(BenefitReward, benefit_id) is None


@pytest.mark.parametrize("target,value", [("fixed_amount", "12.345"), ("percentage", "100.0001")])
def test_reward_precision_and_percentage_upper_bound(
    db_session: Session, graph: Promotion, target: str, value: str
) -> None:
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.execute(
            BenefitReward.__table__.insert().values(
                benefit_id=graph.variants[0].benefits[0].id,
                reward_type="fixed_amount" if target == "fixed_amount" else "percentage",
                **{target: Decimal(value)},
            )
        )


@pytest.mark.parametrize(
    "case", ["benefit_fk", "reward_fk", "product_fk", "duplicate_reward", "duplicate_product"]
)
def test_reward_references_and_uniqueness(db_session: Session, graph: Promotion, case: str) -> None:
    benefit_id = graph.variants[0].benefits[0].id
    product_id = graph.variants[0].product_links[0].product_id
    db_session.execute(
        BenefitReward.__table__.insert().values(
            benefit_id=benefit_id, reward_type="product_specific"
        )
    )
    db_session.execute(
        BenefitProductRewardValue.__table__.insert().values(
            benefit_id=benefit_id, product_id=product_id, amount=Decimal("1")
        )
    )
    with pytest.raises(IntegrityError), db_session.begin_nested():
        if case in ("benefit_fk", "duplicate_reward"):
            db_session.execute(
                BenefitReward.__table__.insert().values(
                    benefit_id=uuid4() if case == "benefit_fk" else benefit_id,
                    reward_type="fixed_amount",
                    fixed_amount=Decimal("1"),
                )
            )
        else:
            db_session.execute(
                BenefitProductRewardValue.__table__.insert().values(
                    benefit_id=uuid4() if case == "reward_fk" else benefit_id,
                    product_id=uuid4() if case == "product_fk" else product_id,
                    amount=Decimal("1"),
                )
            )


@pytest.mark.parametrize("orm_delete", [True, False])
def test_reward_deletion_semantics(db_session: Session, graph: Promotion, orm_delete: bool) -> None:
    benefit = graph.variants[0].benefits[0]
    # An otherwise unreferenced product isolates the reward FK restriction.
    product = Product(manufacturer=graph.manufacturer, name="Reward only", slug="reward-only")
    benefit.reward = BenefitReward(
        reward_type="product_specific",
        product_values=[BenefitProductRewardValue(product=product, amount=Decimal("1.23"))],
    )
    db_session.flush()
    benefit_id, product_id = benefit.id, product.id
    assert product.reward_values
    assert benefit.reward.product_values
    with pytest.raises(IntegrityError), db_session.begin_nested():
        if orm_delete:
            db_session.delete(product)
        else:
            db_session.execute(delete(Product).where(Product.id == product_id))
        db_session.flush()
    if orm_delete:
        db_session.delete(benefit)
    else:
        db_session.execute(delete(Benefit).where(Benefit.id == benefit_id))
    db_session.flush()
    db_session.expire_all()
    assert db_session.get(BenefitReward, benefit_id) is None
    assert db_session.scalar(select(func.count()).select_from(BenefitProductRewardValue)) == 0
    assert db_session.get(Product, product_id) is not None
    db_session.delete(db_session.get(Product, product_id))
    db_session.flush()


def test_invalid_product_value_rolls_back_entire_reward_graph(
    db_session: Session, graph: Promotion
) -> None:
    benefit_id = graph.variants[0].benefits[0].id
    products = [link.product_id for link in graph.variants[0].product_links]
    with pytest.raises(IntegrityError) as error, db_session.begin_nested():
        db_session.execute(
            BenefitReward.__table__.insert().values(
                benefit_id=benefit_id, reward_type="product_specific"
            )
        )
        for product_id, amount in zip(products, ["10.00", "12.345"], strict=True):
            db_session.execute(
                BenefitProductRewardValue.__table__.insert().values(
                    benefit_id=benefit_id, product_id=product_id, amount=Decimal(amount)
                )
            )
    assert error.value.orig.diag.constraint_name == "ck_benefit_product_reward_values_amount"
    assert db_session.get(BenefitReward, benefit_id) is None
    assert db_session.scalar(select(func.count()).select_from(BenefitProductRewardValue)) == 0


@pytest.mark.parametrize("percentage", ["0.0001", "100"])
def test_persisted_percentage_inclusive_valid_boundaries(
    db_session: Session, graph: Promotion, percentage: str
) -> None:
    benefit_id = graph.variants[0].benefits[0].id
    db_session.execute(
        BenefitReward.__table__.insert().values(
            benefit_id=benefit_id, reward_type="percentage", percentage=Decimal(percentage)
        )
    )
    assert db_session.get(BenefitReward, benefit_id).percentage == Decimal(percentage)
