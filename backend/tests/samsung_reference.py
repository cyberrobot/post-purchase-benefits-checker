"""Offline, test-only constructor for one reviewed reference; never imported by app startup."""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.application.identity_matching import IdentityResolver
from app.application.promotion_authoring import (
    parse_candidate_promotion,
    validate_candidate_promotion,
)
from app.application.promotions import change_promotion_status
from app.db.models import (
    Benefit,
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
from app.db.repositories.identity_matching import SqlAlchemyIdentityRepository
from app.domain.identity_normalisation import MatchStatus
from app.domain.promotion_lifecycle import PromotionStatus as S

MANIFEST = Path(__file__).parent / "fixtures/promotions/samsung-summer-wallet-cashback-2026.json"
# Pins reviewed semantic content (JSON formatting/key order are immaterial). A facts change
# requires renewed source review and a deliberate digest update, rather than silent repair.
REVIEWED_SHA256 = "f1de8ffe61ad2f89a375af0225dea6b045cab7997f94ad3fad4c6773b5975027"


def validate_manifest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError):
        raise ValueError("Reference manifest must be reviewed JSON data") from None
    if hashlib.sha256(encoded).hexdigest() != REVIEWED_SHA256:
        raise ValueError("Reference manifest differs from reviewed version 1")
    return value


def reference_manifest():
    return validate_manifest(json.loads(MANIFEST.read_text()))


def _resolve(session, match, kind, attributes):
    if match.status == MatchStatus.AMBIGUOUS:
        raise ValueError("Ambiguous reference identity")
    if match.status == MatchStatus.MATCHED:
        row = session.get(kind, match.canonical_id)
        # Resolved aliases may reuse a differently named canonical identity. Product
        # display identity must still describe the exact reviewed model.
        if kind is Product and row.name != attributes["name"]:
            raise ValueError("Conflicting reference product identity")
        return row
    row = kind(**attributes)
    session.add(row)
    session.flush()
    return row


def _fingerprint(promotion):
    return (
        promotion.name,
        promotion.manufacturer_id,
        promotion.purchase_start_date,
        promotion.purchase_end_date,
        promotion.claim_start_date,
        promotion.claim_end_date,
        promotion.claim_start_offset_days,
        promotion.claim_end_offset_days,
        tuple(
            sorted(
                (
                    v.code,
                    v.name,
                    v.retailer_id,
                    tuple(sorted(link.product_id for link in v.product_links)),
                    tuple(
                        sorted(
                            (
                                b.benefit_type,
                                b.name,
                                b.description,
                                b.reward.reward_type,
                                b.reward.fixed_amount,
                                b.reward.percentage,
                                tuple((r.product_id, r.amount) for r in b.reward.product_values),
                            )
                            for b in v.benefits
                        )
                    ),
                    tuple(sorted((r.requirement_type, r.description) for r in v.requirements)),
                )
                for v in promotion.variants
            )
        ),
        tuple(
            sorted(
                (
                    link.role,
                    link.source.url,
                    link.source.source_type,
                    link.source.title,
                    link.source.retrieved_at,
                    link.source.verified_at,
                )
                for link in promotion.source_links
            )
        ),
    )


def construct_reference(session):
    """Caller owns atomic graph transaction; existing conflicting data is never repaired."""
    f = reference_manifest()
    resolver = IdentityResolver(SqlAlchemyIdentityRepository(session))
    maker = _resolve(
        session,
        resolver.resolve_manufacturer(f["manufacturer"]),
        Manufacturer,
        {"name": f["manufacturer"], "slug": "samsung"},
    )
    shop = _resolve(
        session,
        resolver.resolve_retailer(f["retailer"]),
        Retailer,
        {"name": f["retailer"], "slug": "samsung-com"},
    )
    product = _resolve(
        session,
        resolver.resolve_product(
            f["product"]["model_or_sku"], manufacturer_id=maker.id, retailer_id=shop.id
        ),
        Product,
        {
            "manufacturer_id": maker.id,
            "name": f["product"]["name"],
            "slug": "galaxy-buds4-pro",
            "model_number": f["product"]["model_or_sku"],
        },
    )
    existing = session.scalar(
        select(Promotion)
        .where(Promotion.manufacturer_id == maker.id, Promotion.slug == f["promotion_slug"])
        .with_for_update()
    )
    expected = Promotion(
        manufacturer_id=maker.id,
        name=f["campaign"] + " — SM-R640 at Samsung.com reference",
        slug=f["promotion_slug"],
        status=S.REVIEW,
        purchase_start_date=date.fromisoformat(f["purchase_start_date"]),
        purchase_end_date=date.fromisoformat(f["purchase_end_date"]),
        claim_start_offset_days=0,
        claim_end_offset_days=29,
    )
    expected.variants = [
        PromotionVariant(
            code="buds4-pro-samsung-com",
            name=f["coverage"],
            retailer_id=shop.id,
            product_links=[PromotionVariantProduct(product_id=product.id)],
            benefits=[
                Benefit(
                    benefit_type="cashback",
                    name="GBP 50 cashback",
                    description=" ".join(f["limitations"]),
                    reward=BenefitReward(reward_type="fixed_amount", fixed_amount=Decimal("50.00")),
                )
            ],
            requirements=[
                Requirement(requirement_type=r["type"], description=r["description"])
                for r in f["requirements"]
            ],
        )
    ]
    retrieved = datetime.fromisoformat(f["evidence"]["retrieved_at"])
    verified = datetime.fromisoformat(f["evidence"]["verified_at"])
    expected.source_links = [
        PromotionSource(
            role=role,
            source=Source(
                url=f[key],
                source_type=kind,
                title=title,
                retrieved_at=retrieved,
                verified_at=verified,
            ),
        )
        for role, key, kind, title in (
            (
                "primary",
                "official_terms_url",
                "pdf",
                "Samsung official terms, clauses and tables reviewed",
            ),
            (
                "claim",
                "claim_url",
                "web_page",
                "Claim destination verified in official PDF; portal not accessed",
            ),
            ("supporting", "samsung_newsroom_url", "web_page", "Samsung Newsroom, 15 June 2026"),
        )
    ]
    if existing:
        if existing.status not in (S.REVIEW, S.ACTIVE, S.EXPIRED):
            raise ValueError("Conflicting reference lifecycle state")
        try:
            same = _fingerprint(existing) == _fingerprint(expected)
        except (AttributeError, TypeError):
            same = False
        if not same:
            raise ValueError("Conflicting existing reference graph")
        return existing
    session.add(expected)
    session.flush()
    candidate = parse_candidate_promotion(
        {
            "schema_version": 1,
            "promotion": {
                "manufacturer_id": str(maker.id),
                "name": expected.name,
                "slug": expected.slug,
                "purchase_start_date": f["purchase_start_date"],
                "purchase_end_date": f["purchase_end_date"],
                "claim_window": f["claim_window"],
                "variants": [
                    {
                        "code": expected.variants[0].code,
                        "name": f["coverage"],
                        "retailer_id": str(shop.id),
                        "product_ids": [str(product.id)],
                        "benefits": [{**f["benefit"], "name": "GBP 50 cashback"}],
                        "requirements": f["requirements"],
                    }
                ],
                "sources": [
                    {"source_id": str(link.source_id), "role": link.role}
                    for link in expected.source_links
                ],
            },
        }
    )
    if any(
        issue.code != "unresolved_references"
        for issue in validate_candidate_promotion(candidate).issues
    ):
        raise ValueError("Reference candidate validation failed")
    return expected


def finish_reference(transaction_factory, promotion_id):
    """Resume review/active safely; expired replays do not republish or edit evidence."""
    with transaction_factory() as repository:
        status = repository.get_promotion(promotion_id).status
    if status == S.REVIEW:
        change_promotion_status(transaction_factory, promotion_id, S.ACTIVE)
    if status in (S.REVIEW, S.ACTIVE):
        change_promotion_status(transaction_factory, promotion_id, S.EXPIRED)
