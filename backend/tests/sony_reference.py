"""Offline test-only constructor for a verified Sony reference promotion."""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
)
from app.db.repositories.identity_matching import SqlAlchemyIdentityRepository
from app.domain.identity_normalisation import MatchStatus
from app.domain.promotion_lifecycle import PromotionStatus
from tests.reference_helpers import (
    _fingerprint,
    _resolve,
    _resolve_retailer_with_alias,
    _verified_source,
)

MANIFEST = (
    Path(__file__).parent / "fixtures/promotions/sony-bravia-autumn-cashback-2026-k55xr75m2b.json"
)
REVIEWED_SHA256 = "8703886a35ba0b3536e7a933b8a709b7e2aab9d5910eb41fb4502e5aa129357b"


def _resolve_current(session, match, kind, attributes, *, allow_create=True):
    """Refresh a matched identity before checking reference attributes against it."""
    if match.status == MatchStatus.MATCHED:
        row = session.get(kind, match.canonical_id)
        session.refresh(row)
    return _resolve(session, match, kind, attributes, allow_create=allow_create)


def validate_manifest(value):
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError):
        raise ValueError("Sony manifest must contain valid JSON data") from None
    if not REVIEWED_SHA256 or hashlib.sha256(encoded).hexdigest() != REVIEWED_SHA256:
        raise ValueError("Sony manifest differs from its pinned verified reference")
    if value.get("evidence_status") != "verified":
        raise ValueError("Sony reference requires reviewed official terms evidence")
    for key in (
        "official_terms_url",
        "faq_url",
        "dealer_list_url",
        "claim_url",
    ):
        url = value.get(key)
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("Reference source URLs must use HTTPS")
    return value


def reference_manifest():
    return validate_manifest(json.loads(MANIFEST.read_text()))


def source_observations(manifest):
    """Pure mapping of each reviewed source's metadata; no pin bypass or writes."""
    evidence = manifest["evidence"]
    common_times = {key: evidence[key] for key in ("retrieved_at", "verified_at")}
    observations = {
        "primary": {
            "url": manifest["official_terms_url"],
            "source_type": "pdf",
            "title_or_version": f"Sony BRAVIA Autumn Cashback terms — {evidence['terms_version']}",
            **common_times,
        },
        "claim": {
            "url": manifest["claim_url"],
            "source_type": "web_page",
            "title_or_version": evidence["claim_source_title"],
            **common_times,
        },
        "supporting": dict(evidence["supporting_source"]),
    }
    if (
        observations["supporting"]["url"] != manifest["dealer_list_url"]
        or observations["supporting"]["source_type"] != "pdf"
    ):
        raise ValueError("Inconsistent supporting dealer evidence")
    for observation in observations.values():
        try:
            times = [
                datetime.fromisoformat(observation[key]) for key in ("retrieved_at", "verified_at")
            ]
        except (ValueError, TypeError):
            raise ValueError("Observed source timestamps must be valid ISO timestamps") from None
        if any(value.tzinfo is None or value.utcoffset() is None for value in times):
            raise ValueError("Observed source timestamps must be timezone-aware")
        if times[1] < times[0]:
            raise ValueError("Observed source verification must not precede retrieval")
    return observations


def construct_reference(session):
    """Construct in review; callers publish through the persisted publication gate."""
    if session.new or session.dirty or session.deleted:
        raise ValueError("Reference construction requires a session without pending changes")
    f = reference_manifest()
    observations = source_observations(f)
    with session.begin_nested():
        resolver = IdentityResolver(SqlAlchemyIdentityRepository(session))
        maker = _resolve_current(
            session,
            resolver.resolve_manufacturer(f["manufacturer"]),
            Manufacturer,
            {"name": f["manufacturer"], "slug": "sony"},
        )
        existing = session.scalar(
            select(Promotion)
            .where(
                Promotion.manufacturer_id == maker.id,
                Promotion.slug == f["promotion_slug"],
            )
            .options(
                selectinload(Promotion.variants).selectinload(PromotionVariant.product_links),
                selectinload(Promotion.variants)
                .selectinload(PromotionVariant.benefits)
                .selectinload(Benefit.reward)
                .selectinload(BenefitReward.product_values),
                selectinload(Promotion.variants).selectinload(PromotionVariant.requirements),
                selectinload(Promotion.source_links).selectinload(PromotionSource.source),
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        shop = _resolve_retailer_with_alias(
            session,
            resolver,
            canonical_name="Currys",
            canonical_slug="currys",
            observed_name=f["retailer"],
            allow_create=existing is None,
        )
        product = _resolve_current(
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
                "slug": "bravia-7-ii-k55xr75m2b",
                "model_number": f["product"]["model_or_sku"],
            },
            allow_create=existing is None,
        )
        expected = Promotion(
            manufacturer_id=maker.id,
            name=f["campaign"] + " — K55XR75M2B at Currys UK reference",
            slug=f["promotion_slug"],
            status=PromotionStatus.REVIEW,
            purchase_start_date=date.fromisoformat(f["purchase_start_date"]),
            purchase_end_date=date.fromisoformat(f["purchase_end_date"]),
            claim_start_date=date.fromisoformat(f["claim_window"]["start_date"]),
            claim_end_date=date.fromisoformat(f["claim_window"]["end_date"]),
            claim_min_wait_days=f["claim_window"]["minimum_days_after_purchase"],
        )
        expected.variants = [
            PromotionVariant(
                code="k55xr75m2b-currys-uk",
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
                        name="GBP 150.00 cashback",
                        description=" ".join(
                            [
                                f["limitations"][0],
                                *f["limitations"][2:],
                                "The 35-day wait after each purchase is enforced "
                                "with the fixed campaign deadline.",
                            ]
                        ),
                        reward=BenefitReward(
                            reward_type="fixed_amount", fixed_amount=Decimal("150.00")
                        ),
                    )
                ],
            )
        ]
        # Flush source observations before transient FK-only associations.
        sources = {
            role: _verified_source(session, observation)
            for role, observation in observations.items()
        }
        expected.source_links = [
            PromotionSource(role=role, source_id=source.id) for role, source in sources.items()
        ]
        if existing:
            if existing.status not in (
                PromotionStatus.REVIEW,
                PromotionStatus.ACTIVE,
                PromotionStatus.EXPIRED,
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
                                    "name": "GBP 150.00 cashback",
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
