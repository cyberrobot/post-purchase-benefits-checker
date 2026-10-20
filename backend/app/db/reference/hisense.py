"""Offline review-only constructor for a verified Hisense reference promotion."""

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
)
from app.db.reference.helpers import _fingerprint, _resolve, _verified_source
from app.db.repositories.identity_matching import SqlAlchemyIdentityRepository
from app.domain.promotion_lifecycle import PromotionStatus

MANIFEST = (
    Path(__file__).parents[2] / "data/reference/hisense-autumn-cashback-2026-wf7i1248bbr.json"
)
REVIEWED_SHA256 = "991139c7dfcc4938d25ffb1563a3a9aad694a4d4fc6474e69650b3594daea450"


def validate_manifest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError):
        raise ValueError("Hisense manifest must contain valid JSON data") from None
    if not REVIEWED_SHA256 or hashlib.sha256(encoded).hexdigest() != REVIEWED_SHA256:
        raise ValueError("Hisense manifest differs from its pinned verified reference")
    if value.get("evidence_status") != "verified":
        raise ValueError("Hisense reference requires reviewed official terms evidence")
    for key in (
        "official_terms_url",
        "retailer_corroboration_url",
        "claim_url",
    ):
        url = value.get(key)
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("Reference source URLs must use HTTPS")
    return value


def reference_manifest():
    return validate_manifest(json.loads(MANIFEST.read_text()))


def construct_reference(session):
    """Construct in review; callers publish through the persisted publication gate."""
    if session.new or session.dirty or session.deleted:
        raise ValueError("Reference construction requires a session without pending changes")
    f = reference_manifest()
    with session.begin_nested():
        resolver = IdentityResolver(SqlAlchemyIdentityRepository(session))
        maker = _resolve(
            session,
            resolver.resolve_manufacturer(f["manufacturer"]),
            Manufacturer,
            {"name": f["manufacturer"], "slug": "hisense"},
        )
        existing = session.scalar(
            select(Promotion)
            .where(
                Promotion.manufacturer_id == maker.id,
                Promotion.slug == f["promotion_slug"],
            )
            .with_for_update()
        )
        shop = _resolve(
            session,
            resolver.resolve_retailer(f["retailer"]),
            Retailer,
            {"name": f["retailer"], "slug": "currys"},
            allow_create=existing is None,
        )
        product = _resolve(
            session,
            resolver.resolve_product(
                f["product"]["model_or_sku"],
                manufacturer_id=maker.id,
                retailer_id=shop.id,
            ),
            Product,
            {
                "manufacturer_id": maker.id,
                "name": f["product"]["name"],
                "slug": "kitchenfit-7i-wf7i1248bbr",
                "model_number": f["product"]["model_or_sku"],
            },
            allow_create=existing is None,
        )
        expected = Promotion(
            manufacturer_id=maker.id,
            name=f["campaign"] + " — WF7I1248BBR at Currys reference",
            slug=f["promotion_slug"],
            status=PromotionStatus.REVIEW,
            purchase_start_date=date.fromisoformat(f["purchase_start_date"]),
            purchase_end_date=date.fromisoformat(f["purchase_end_date"]),
            claim_start_date=date.fromisoformat(f["claim_window"]["start_date"]),
            claim_end_date=date.fromisoformat(f["claim_window"]["end_date"]),
        )
        expected.variants = [
            PromotionVariant(
                code="wf7i1248bbr-currys",
                name=f["coverage"],
                retailer_id=shop.id,
                product_links=[PromotionVariantProduct(product_id=product.id)],
                requirements=[
                    Requirement(requirement_type=r["type"], description=r["description"])
                    for r in f["requirements"]
                ],
                benefits=[
                    Benefit(
                        benefit_type="cashback",
                        name="GBP 100.00 cashback",
                        description=" ".join(f["limitations"]),
                        reward=BenefitReward(
                            reward_type="fixed_amount", fixed_amount=Decimal("100.00")
                        ),
                    )
                ],
            )
        ]
        evidence = f["evidence"]
        retrieved_at = datetime.fromisoformat(evidence["retrieved_at"])
        verified_at = datetime.fromisoformat(evidence["verified_at"])
        # Resolve and flush source observations before creating any transient links.
        # FK-only links avoid appending an unsaved graph to persistent source backrefs.
        sources = {
            role: _verified_source(
                session,
                {
                    "url": url,
                    "source_type": "web_page",
                    "title_or_version": title,
                    "retrieved_at": retrieved_at.isoformat(),
                    "verified_at": verified_at.isoformat(),
                },
            )
            for role, url, title in (
                (
                    "primary",
                    f["official_terms_url"],
                    f"Hisense Autumn Cashback terms — {evidence['terms_version']}",
                ),
                (
                    "claim",
                    f["claim_url"],
                    evidence["claim_source_title"],
                ),
            )
        }
        expected.source_links = [
            PromotionSource(role=role, source_id=source.id) for role, source in sources.items()
        ]
        if existing:
            if existing.status not in (
                PromotionStatus.REVIEW,
                PromotionStatus.ACTIVE,
                PromotionStatus.EXPIRED,
                PromotionStatus.ARCHIVED,
            ):
                raise ValueError("Incompatible reference lifecycle")
            try:
                with session.no_autoflush:
                    same = _fingerprint(existing) == _fingerprint(
                        expected, {source.id: source for source in sources.values()}
                    )
            except (AttributeError, TypeError):
                same = False
            if not same:
                raise ValueError("Conflicting existing verified reference")
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
                            "benefits": [
                                {
                                    "type": "cashback",
                                    "name": "GBP 100.00 cashback",
                                    "reward": f["benefit"]["reward"],
                                }
                            ],
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
        issues = validate_candidate_promotion(candidate).issues
        if any(issue.code != "unresolved_references" for issue in issues):
            raise ValueError("Verified reference candidate validation failed")
        return expected
