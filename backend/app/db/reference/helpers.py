"""Manufacturer-neutral helpers for offline reviewed reference fixtures."""

from datetime import datetime

from sqlalchemy import select

from app.db.models import Product, Source
from app.domain.identity_normalisation import MatchStatus, normalise_identifier


def _resolve(session, match, kind, attributes, *, allow_create=True):
    if match.status == MatchStatus.AMBIGUOUS:
        raise ValueError("Ambiguous reference identity")
    if match.status == MatchStatus.MATCHED:
        row = session.get(kind, match.canonical_id)
        if kind is Product and (
            row.manufacturer_id != attributes["manufacturer_id"]
            or normalise_identifier(row.model_number or "")
            != normalise_identifier(attributes["model_number"])
        ):
            raise ValueError("Conflicting reference product identity")
        return row
    if not allow_create:
        raise ValueError("Conflicting existing reference graph: missing identity")
    row = kind(**attributes)
    session.add(row)
    session.flush()
    return row


def _fingerprint(promotion, sources_by_id=None):
    def source_for(link):
        return sources_by_id[link.source_id] if sources_by_id is not None else link.source

    return (
        promotion.name,
        promotion.manufacturer_id,
        promotion.purchase_start_date,
        promotion.purchase_end_date,
        promotion.claim_start_date,
        promotion.claim_end_date,
        promotion.claim_start_offset_days,
        promotion.claim_end_offset_days,
        promotion.claim_min_wait_days,
        tuple(
            sorted(
                (
                    variant.code,
                    variant.name,
                    variant.retailer_id,
                    tuple(sorted(link.product_id for link in variant.product_links)),
                    tuple(
                        sorted(
                            (
                                benefit.benefit_type,
                                benefit.name,
                                benefit.description,
                                benefit.reward.reward_type,
                                benefit.reward.fixed_amount,
                                benefit.reward.percentage,
                                tuple(
                                    sorted(
                                        (v.product_id, v.amount)
                                        for v in benefit.reward.product_values
                                    )
                                ),
                            )
                            for benefit in variant.benefits
                        )
                    ),
                    tuple(
                        sorted(
                            (item.requirement_type, item.description)
                            for item in variant.requirements
                        )
                    ),
                )
                for variant in promotion.variants
            )
        ),
        tuple(
            sorted(
                (
                    link.role,
                    source_for(link).url,
                    source_for(link).source_type,
                    source_for(link).title,
                    source_for(link).retrieved_at,
                    source_for(link).verified_at,
                )
                for link in promotion.source_links
            )
        ),
    )


def _verified_source(session, observation):
    """Reuse only a source record whose URL, role evidence and timestamps all agree."""
    retrieved_at = datetime.fromisoformat(observation["retrieved_at"])
    if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
        raise ValueError("Observed source retrieval time must be timezone-aware")
    criteria = (
        Source.url == observation["url"],
        Source.source_type == observation["source_type"],
        Source.title == observation["title_or_version"],
        Source.retrieved_at == retrieved_at,
        Source.verified_at == datetime.fromisoformat(observation["verified_at"]),
    )
    rows = list(session.scalars(select(Source).where(*criteria).with_for_update()))
    if len(rows) > 1:
        raise ValueError("Ambiguous identical verified reference source observations")
    if rows:
        return rows[0]
    source = Source(
        url=observation["url"],
        source_type=observation["source_type"],
        title=observation["title_or_version"],
        retrieved_at=retrieved_at,
        verified_at=datetime.fromisoformat(observation["verified_at"]),
    )
    session.add(source)
    session.flush()
    return source


def _resolve_retailer_with_alias(
    session, resolver, *, canonical_name, canonical_slug, observed_name, allow_create=True
):
    """Bind a reviewed dealer label to one canonical identity, never merge owners."""
    from app.db.models import Retailer, RetailerAlias
    from app.domain.identity_normalisation import normalise_text

    canonical = resolver.resolve_retailer(canonical_name)
    observed = resolver.resolve_retailer(observed_name)
    if MatchStatus.AMBIGUOUS in (canonical.status, observed.status):
        raise ValueError("Ambiguous reference retailer identity")
    if observed.status == MatchStatus.MATCHED and (
        canonical.status != MatchStatus.MATCHED or observed.canonical_id != canonical.canonical_id
    ):
        raise ValueError("Conflicting reference retailer identities or dealer alias")
    retailer = _resolve(
        session,
        canonical,
        Retailer,
        {"name": canonical_name, "slug": canonical_slug},
        allow_create=allow_create,
    )
    # Serialize alias creation on the canonical owner for fixture participants.
    session.refresh(retailer, with_for_update=True)
    observed = resolver.resolve_retailer(observed_name)
    if observed.status == MatchStatus.AMBIGUOUS:
        raise ValueError("Ambiguous reference retailer identity")
    if observed.status == MatchStatus.MATCHED and observed.canonical_id != retailer.id:
        raise ValueError("Conflicting reference retailer identities or dealer alias")
    alias_key = normalise_text(observed_name)
    if observed.status == MatchStatus.NOT_FOUND:
        session.add(RetailerAlias(retailer_id=retailer.id, alias=observed_name))
        session.flush()
    elif session.get(RetailerAlias, (retailer.id, alias_key)) is None:
        # A canonical name/slug match already resolves the label; no alias is needed.
        if alias_key not in (normalise_text(retailer.name), normalise_text(retailer.slug)):
            raise ValueError("Conflicting reference retailer alias")
    return retailer
