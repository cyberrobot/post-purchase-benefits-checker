"""Offline test-only constructor for an explicitly unverified Hisense candidate."""

import hashlib
import json
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from app.application.identity_matching import IdentityResolver
from app.application.promotion_authoring import parse_candidate_promotion, validate_candidate_promotion
from app.db.models import (
    Benefit,
    BenefitReward,
    Manufacturer,
    Product,
    Promotion,
    PromotionSource,
    PromotionVariant,
    PromotionVariantProduct,
    Retailer,
    Source,
)
from app.db.repositories.identity_matching import SqlAlchemyIdentityRepository
from app.domain.identity_normalisation import MatchStatus
from app.domain.promotion_lifecycle import PromotionStatus
from sqlalchemy import select

MANIFEST = Path(__file__).parent / "fixtures/promotions/hisense-autumn-cashback-2026-wf7i1248bbr.json"
REVIEWED_SHA256 = "05a90a76de90cd27674a0c9f3751c79f9a98386a03c9c0806111748a70fed254"


def validate_manifest(value):
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    if not REVIEWED_SHA256 or hashlib.sha256(encoded).hexdigest() != REVIEWED_SHA256:
        raise ValueError("Hisense manifest differs from its pinned unverified review candidate")
    if value.get("evidence_status") != "unverified_review_candidate":
        raise ValueError("Hisense evidence has not passed the required full terms review")
    for key in ("official_terms_url", "manufacturer_campaign_url", "retailer_corroboration_url", "claim_url"):
        url = value.get(key)
        if not isinstance(url, str) or not url.startswith("https://"):
            raise ValueError("Reference source URLs must use HTTPS")
    if value["evidence"]["observations"][0]["verified_at"] is not None:
        raise ValueError("Challenged terms cannot be marked verified")
    return value


def reference_manifest():
    return validate_manifest(json.loads(MANIFEST.read_text()))


def _resolve(session, match, kind, attributes, *, allow_create=True):
    if match.status == MatchStatus.AMBIGUOUS:
        raise ValueError("Ambiguous reference identity")
    if match.status == MatchStatus.MATCHED:
        row = session.get(kind, match.canonical_id)
        if kind is Product and row.name != attributes["name"]:
            raise ValueError("Conflicting reference product identity")
        return row
    if not allow_create:
        raise ValueError("Conflicting existing reference graph: missing identity")
    row = kind(**attributes)
    session.add(row)
    session.flush()
    return row


def _fingerprint(promotion):
    return (
        promotion.name, promotion.manufacturer_id, promotion.purchase_start_date,
        promotion.purchase_end_date, promotion.claim_start_date, promotion.claim_end_date,
        promotion.claim_start_offset_days, promotion.claim_end_offset_days,
        tuple(sorted((
            variant.code, variant.name, variant.retailer_id,
            tuple(sorted(link.product_id for link in variant.product_links)),
            tuple(sorted((
                benefit.benefit_type, benefit.name, benefit.description,
                benefit.reward.reward_type, benefit.reward.fixed_amount,
            ) for benefit in variant.benefits)),
            tuple(sorted((item.requirement_type, item.description) for item in variant.requirements)),
        ) for variant in promotion.variants)),
        tuple(sorted((
            link.role, link.source.url, link.source.source_type, link.source.title,
            link.source.retrieved_at, link.source.verified_at,
        ) for link in promotion.source_links)),
    )


def construct_reference(session):
    """Build only a review graph; publication must fail until evidence is re-reviewed."""
    if session.new or session.dirty or session.deleted:
        raise ValueError("Reference construction requires a session without pending changes")
    f = reference_manifest()
    with session.begin_nested():
        resolver = IdentityResolver(SqlAlchemyIdentityRepository(session))
        maker = _resolve(
            session, resolver.resolve_manufacturer(f["manufacturer"]), Manufacturer,
            {"name": f["manufacturer"], "slug": "hisense"},
        )
        existing = session.scalar(
            select(Promotion).where(
                Promotion.manufacturer_id == maker.id, Promotion.slug == f["promotion_slug"]
            ).with_for_update()
        )
        shop = _resolve(
            session, resolver.resolve_retailer(f["retailer"]), Retailer,
            {"name": f["retailer"], "slug": "currys"}, allow_create=existing is None,
        )
        product = _resolve(
            session,
            resolver.resolve_product(
                f["product"]["model_or_sku"], manufacturer_id=maker.id, retailer_id=shop.id
            ),
            Product,
            {"manufacturer_id": maker.id, "name": f["product"]["name"],
             "slug": "kitchenfit-7i-wf7i1248bbr", "model_number": f["product"]["model_or_sku"]},
            allow_create=existing is None,
        )
        expected = Promotion(
            manufacturer_id=maker.id,
            name=f["campaign"] + " — WF7I1248BBR at Currys unverified candidate",
            slug=f["promotion_slug"],
            status=PromotionStatus.REVIEW,
            purchase_start_date=date.fromisoformat(f["purchase_start_date"]),
            purchase_end_date=date.fromisoformat(f["purchase_end_date"]),
            claim_start_date=date.fromisoformat(f["claim_window"]["start_date"]),
            claim_end_date=date.fromisoformat(f["claim_window"]["end_date"]),
        )
        expected.variants = [PromotionVariant(
            code="wf7i1248bbr-currys",
            name=f["coverage"],
            retailer_id=shop.id,
            product_links=[PromotionVariantProduct(product_id=product.id)],
            benefits=[Benefit(
                benefit_type="cashback",
                name="Proposed GBP 100.00 cashback (unverified)",
                description=" ".join(f["limitations"]),
                reward=BenefitReward(reward_type="fixed_amount", fixed_amount=Decimal("100.00")),
            )],
        )]
        retrieved = datetime.fromisoformat("2026-10-09T12:29:00+00:00")
        expected.source_links = [
            PromotionSource(role="primary", source=Source(
                url=f["official_terms_url"], source_type="web_page",
                title="Autumn 2026 terms endpoint challenged; not reviewed", retrieved_at=retrieved,
                verified_at=None,
            )),
            PromotionSource(role="supporting", source=Source(
                url=f["retailer_corroboration_url"], source_type="web_page",
                title="Currys product page partially reviewed; campaign facts unverified",
                retrieved_at=retrieved, verified_at=None,
            )),
            PromotionSource(role="claim", source=Source(
                url=f["claim_url"], source_type="web_page",
                title="Proposed claim destination; not independently verified",
                retrieved_at=retrieved, verified_at=None,
            )),
        ]
        if existing:
            if existing.status != PromotionStatus.REVIEW:
                raise ValueError("Unverified Hisense candidate cannot be replayed after publication")
            try:
                same = _fingerprint(existing) == _fingerprint(expected)
            except (AttributeError, TypeError):
                same = False
            if not same:
                raise ValueError("Conflicting existing unverified reference candidate")
            return existing
        session.add(expected)
        session.flush()
        candidate = parse_candidate_promotion({
            "schema_version": 1,
            "promotion": {
                "manufacturer_id": str(maker.id), "name": expected.name,
                "slug": expected.slug, "purchase_start_date": f["purchase_start_date"],
                "purchase_end_date": f["purchase_end_date"], "claim_window": f["claim_window"],
                "variants": [{
                    "code": expected.variants[0].code, "name": f["coverage"],
                    "retailer_id": str(shop.id), "product_ids": [str(product.id)],
                    "benefits": [{"type": "cashback", "name": "Proposed GBP 100.00 cashback (unverified)",
                                  "reward": f["benefit"]["reward"]}],
                    "requirements": [],
                }],
                "sources": [{"source_id": str(link.source_id), "role": link.role}
                            for link in expected.source_links],
            },
        })
        issues = validate_candidate_promotion(candidate).issues
        if any(issue.code != "unresolved_references" for issue in issues):
            raise ValueError("Unverified reference candidate preflight failed")
        return expected
