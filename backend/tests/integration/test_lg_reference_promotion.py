from datetime import date, datetime
from decimal import Decimal
from functools import partial

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from app.api.eligibility import uk_evaluation_date
from app.application.promotion_candidate_matching import UnresolvedPurchaseIdentity
from app.application.promotions import PromotionPublicationError, change_promotion_status
from app.application.purchase_check import CheckPurchaseRequest, check_purchase
from app.application.purchase_check_details import CheckPurchaseResult, NoMatchReason
from app.core.config import Settings
from app.db.models import Manufacturer, Product, Promotion, Retailer, Source
from app.db.repositories.promotions import promotion_transaction, purchase_check_snapshot
from app.domain.promotion_lifecycle import PromotionStatus as S
from app.main import create_app
from tests.integration.test_promotion_lifecycle import snapshot, transaction
from tests.lg_reference import construct_reference, finish_reference, reference_manifest

pytestmark = pytest.mark.integration


@pytest.fixture
def reference(postgres_engine, migrated_test_database):
    factory = sessionmaker(postgres_engine)
    with factory.begin() as session:
        owned_types = (Promotion, Source, Product, Retailer, Manufacturer)
        before = {kind: set(session.scalars(select(kind.id))) for kind in owned_types}
        promotion = construct_reference(session)
        identity = promotion.id
        maker_id = promotion.manufacturer_id
        # Fake identities are intentionally separate from official campaign facts.
        other_shop = Retailer(name="Excluded test retailer", slug="excluded-test-retailer")
        other_product = Product(
            manufacturer_id=maker_id,
            name="Unlinked test model",
            slug="unlinked-test-model",
            model_number="TEST-NOT-OLED55G54LW.AEK",
        )
        session.add_all([other_shop, other_product])
        session.flush()
        owned = {kind: set(session.scalars(select(kind.id))) - before[kind] for kind in owned_types}
    try:
        finish_reference(partial(promotion_transaction, factory), identity)
        yield factory, identity
    finally:
        with factory.begin() as session:
            delete_owned_rows(session, owned)


def delete_owned_rows(session, owned):
    """Delete only fixture-owned graph/identity rows, in foreign-key order."""
    for kind in (Promotion, Source, Product, Retailer, Manufacturer):
        if owned[kind]:
            session.execute(delete(kind).where(kind.id.in_(owned[kind])))


def check(
    factory,
    purchase,
    evaluation,
    model="OLED55G54LW.AEK",
    retailer="LG.com/UK",
    purchase_price=None,
):
    with purchase_check_snapshot(factory) as (resolver, repository):
        return check_purchase(
            CheckPurchaseRequest("LG", model, retailer, purchase, purchase_price),
            evaluation_date=evaluation,
            identity_resolver=resolver,
            promotion_repository=repository,
        )


@pytest.mark.parametrize(
    "purchase,evaluation,classification",
    [
        ("2025-05-21", "2025-05-21", "ELIGIBLE"),
        ("2025-05-21", "2025-05-22", "ELIGIBLE"),
        ("2025-06-24", "2025-06-24", "ELIGIBLE"),
        ("2025-06-24", "2025-08-18", "ELIGIBLE"),
        ("2025-06-24", "2025-08-19", "ELIGIBLE"),
        ("2025-06-24", "2025-08-20", "EXPIRED"),
        ("2025-06-24", "2026-10-09", "EXPIRED"),
    ],
)
def test_real_published_snapshot_boundaries(reference, purchase, evaluation, classification):
    factory, identity = reference
    f = reference_manifest()
    purchase = date.fromisoformat(purchase)
    result = check(factory, purchase, date.fromisoformat(evaluation))
    assert isinstance(result, CheckPurchaseResult) and result.no_match_reason is None
    assert len(result.promotions) == 1
    offer = result.promotions[0]
    assert offer.promotion_id == identity and offer.promotion_status == S.EXPIRED
    assert offer.eligibility.classification == classification
    assert [r.code for r in offer.eligibility.reasons] == [
        "all_configured_rules_satisfied",
        "claim_window_open" if classification == "ELIGIBLE" else "claim_window_expired",
    ]
    assert offer.claim_window.opens_on == date(2025, 5, 21)
    assert offer.claim_window.deadline_on == date(2025, 8, 19)
    assert len(offer.benefits) == 1
    assert offer.benefits[0].cashback_reward_gbp == Decimal("150.00")
    assert offer.benefits[0].reward_unavailable_reason is None
    assert "does not guarantee" in offer.benefits[0].benefit.description
    assert {r.requirement_type for r in offer.requirements} == {"receipt", "serial_number"}
    assert any("readable serial number" in r.description for r in offer.requirements)
    assert offer.provenance.official_source_url == f["official_terms_url"]
    assert offer.provenance.claim_url == f["claim_url"]
    assert {s.role for s in offer.sources} == {"primary", "claim"}
    assert {s.url for s in offer.sources} == {f[k] for k in ("official_terms_url", "claim_url")}
    assert all(s.retrieved_at.tzinfo and s.verified_at >= s.retrieved_at for s in offer.sources)
    assert offer.explanation == (
        "The recorded eligibility rules match this purchase.",
        "The claim window is open."
        if classification == "ELIGIBLE"
        else "The claim deadline has passed.",
    )


@pytest.mark.parametrize(
    "purchase,evaluation,model,retailer",
    [
        ("2025-05-20", "2025-05-21", "OLED55G54LW.AEK", "LG.com/UK"),
        ("2025-06-25", "2025-06-25", "OLED55G54LW.AEK", "LG.com/UK"),
        ("2025-06-01", "2025-06-01", "OLED55G54LW.AEK", "Excluded test retailer"),
        ("2025-06-01", "2025-06-01", "TEST-NOT-OLED55G54LW.AEK", "LG.com/UK"),
    ],
)
def test_resolved_exclusions_are_no_match(reference, purchase, evaluation, model, retailer):
    result = check(
        reference[0], date.fromisoformat(purchase), date.fromisoformat(evaluation), model, retailer
    )
    assert isinstance(result, CheckPurchaseResult)
    assert result.promotions == ()
    assert result.no_match_reason == NoMatchReason.NO_MATCHING_PUBLISHED_PROMOTIONS


@pytest.mark.parametrize("resume", [S.REVIEW, S.ACTIVE, S.EXPIRED])
def test_publication_resume_and_replay_preserve_all_reference_data(db_session, resume):
    with db_session.begin_nested():
        promotion = construct_reference(db_session)
    operation = partial(transaction, db_session)
    if resume != S.REVIEW:
        change_promotion_status(operation, promotion.id, S.ACTIVE)
    if resume == S.EXPIRED:
        change_promotion_status(operation, promotion.id, S.EXPIRED)
    before = snapshot(db_session)
    assert construct_reference(db_session).id == promotion.id
    finish_reference(operation, promotion.id)
    db_session.expire_all()
    assert db_session.get(Promotion, promotion.id).status == S.EXPIRED
    after = snapshot(db_session)
    assert all(before[t] == after[t] for t in before.keys() - {"promotions"})
    assert construct_reference(db_session).id == promotion.id
    finish_reference(operation, promotion.id)
    assert snapshot(db_session) == after


@pytest.mark.parametrize(
    "role", ["primary", "claim", "missing_primary", "missing_claim", "manufacturer"]
)
def test_invalid_review_graph_cannot_publish(db_session, role):
    promotion = construct_reference(db_session)
    if role == "manufacturer":
        other = Manufacturer(name="Other test maker", slug="other-test-maker")
        product = Product(manufacturer=other, name="Wrong maker model", slug="wrong-maker-model")
        from app.db.models import PromotionVariantProduct

        promotion.variants[0].product_links.append(PromotionVariantProduct(product=product))
        code = "product_manufacturer_mismatch"
    elif role.startswith("missing_"):
        missing_role = role.removeprefix("missing_")
        db_session.delete(
            next(link for link in promotion.source_links if link.role == missing_role)
        )
        code = f"missing_{missing_role}_source"
        db_session.flush()
        db_session.expire(promotion, ["source_links"])
    else:
        next(link.source for link in promotion.source_links if link.role == role).verified_at = None
        code = f"{role}_source_unverified"
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(PromotionPublicationError) as error:
        change_promotion_status(partial(transaction, db_session), promotion.id, S.ACTIVE)
    assert code in {issue.code for issue in error.value.report.issues}
    assert snapshot(db_session) == before
    assert db_session.get(Promotion, promotion.id).status == S.REVIEW


def test_conflicting_graph_fails_without_replacement(db_session):
    promotion = construct_reference(db_session)
    promotion.variants[0].benefits[0].reward.fixed_amount = Decimal("99.00")
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(ValueError, match="Conflicting"):
        construct_reference(db_session)
    assert snapshot(db_session) == before


def test_atomic_construction_failure_rolls_back_and_retry_succeeds(db_session, monkeypatch):
    from tests import lg_reference as helper

    before = snapshot(db_session)
    original = helper.validate_candidate_promotion

    def fail(candidate):
        raise ValueError("simulated candidate validation failure")

    monkeypatch.setattr(helper, "validate_candidate_promotion", fail)
    with pytest.raises(ValueError, match="simulated"), db_session.begin_nested():
        construct_reference(db_session)
    assert snapshot(db_session) == before
    monkeypatch.setattr(helper, "validate_candidate_promotion", original)
    with db_session.begin_nested():
        promotion = construct_reference(db_session)
    finish_reference(partial(transaction, db_session), promotion.id)
    db_session.expire_all()
    assert db_session.get(Promotion, promotion.id).status == S.EXPIRED


def test_http_existing_route_historical_and_no_match(reference, postgres_engine):
    app = create_app(
        Settings(_env_file=None, APP_ENV="test", DATABASE_URL="postgresql+psycopg://unused/unused"),
        engine_factory=lambda _: postgres_engine,
    )
    app.dependency_overrides[uk_evaluation_date] = lambda: date(2025, 8, 19)
    with TestClient(app) as client:
        body = {
            "brand": "LG",
            "model": "OLED55G54LW.AEK",
            "retailer": "LG.com/UK",
            "purchase_date": "2025-06-24",
        }
        response = client.post("/api/v1/eligibility/check", json=body)
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/json"
        offer = response.json()["promotions"][0]
        assert offer["promotion_status"] == "expired"
        assert offer["eligibility"]["classification"] == "ELIGIBLE"
        assert offer["benefits"][0]["cashback_reward_gbp"] == "150.00"
        assert offer["claim_window"]["deadline_on"] == "2025-08-19"
        assert {r["requirement_type"] for r in offer["requirements"]} == {
            "receipt",
            "serial_number",
        }
        f = reference_manifest()
        assert offer["provenance"]["official_source_url"] == f["official_terms_url"]
        assert offer["provenance"]["claim_url"] == f["claim_url"]
        app.dependency_overrides[uk_evaluation_date] = lambda: date(2025, 8, 20)
        expired = client.post("/api/v1/eligibility/check", json=body)
        assert expired.status_code == 200
        assert expired.json()["promotions"][0]["eligibility"]["classification"] == "EXPIRED"
        outside = client.post(
            "/api/v1/eligibility/check", json={**body, "purchase_date": "2025-06-25"}
        )
        assert outside.status_code == 200
        assert outside.json()["promotions"] == []
        assert outside.json()["no_match_reason"] == "no_matching_published_promotions"
        response = client.post(
            "/api/v1/eligibility/check", json={**body, "retailer": "Excluded test retailer"}
        )
        assert response.status_code == 200
        assert response.json()["promotions"] == []
        assert response.json()["no_match_reason"] == "no_matching_published_promotions"


def test_snapshot_reproducible_read_only_without_http(reference, postgres_engine, monkeypatch):
    import httpx
    from sqlalchemy import event

    def forbidden_http(*args, **kwargs):
        raise AssertionError("Reference purchase checks must not retrieve remote evidence")

    monkeypatch.setattr(httpx.Client, "send", forbidden_http)
    statements = []

    def record(connection, cursor, statement, *args):
        statements.append(statement.lstrip().split()[0].upper())

    event.listen(postgres_engine, "before_cursor_execute", record)
    try:
        first = check(reference[0], date(2025, 6, 24), date(2025, 8, 19))
        assert check(reference[0], date(2025, 6, 24), date(2025, 8, 19)) == first
        assert not {"INSERT", "UPDATE", "DELETE"}.intersection(statements)
    finally:
        event.remove(postgres_engine, "before_cursor_execute", record)


def test_canonical_aliases_reused_without_duplicate_identities(db_session):
    from app.db.models import ManufacturerAlias, ProductModelAlias, RetailerAlias

    maker = Manufacturer(name="LG Electronics", slug="lg-electronics")
    shop = Retailer(name="LG online UK", slug="lg-online-uk")
    product = Product(
        manufacturer=maker,
        name="LG OLED G5 55-inch TV",
        slug="oled55g54lw-aek",
        model_number="OLED55G54LW.AEK",
    )
    db_session.add_all([maker, shop, product])
    db_session.flush()
    db_session.add_all(
        [
            ManufacturerAlias(manufacturer_id=maker.id, alias="LG"),
            RetailerAlias(retailer_id=shop.id, alias="LG.com/UK"),
            ProductModelAlias(product_id=product.id, alias="OLED55G54LW.AEK"),
        ]
    )
    db_session.flush()
    promotion = construct_reference(db_session)
    assert promotion.manufacturer_id == maker.id
    assert promotion.variants[0].retailer_id == shop.id
    assert promotion.variants[0].product_links[0].product_id == product.id
    from sqlalchemy import func

    assert db_session.scalar(select(func.count()).select_from(Manufacturer)) == 1
    assert db_session.scalar(select(func.count()).select_from(Product)) == 1
    assert db_session.scalar(select(func.count()).select_from(Retailer)) == 1


@pytest.mark.parametrize("case", ["ambiguous", "wrong_suffix"])
def test_ambiguous_or_mislabelled_product_identity_is_rejected(db_session, case):
    maker = Manufacturer(name="LG", slug="lg")
    shop = Retailer(name="LG.com/UK", slug="lg-com-uk")
    products = [
        Product(
            manufacturer=maker,
            name="LG OLED G5 55-inch TV",
            slug="existing-lg-model",
            model_number="OLED55G54LW" if case == "wrong_suffix" else "OLED55G54LW.AEK",
        )
    ]
    if case == "ambiguous":
        products.append(
            Product(
                manufacturer=maker, name="Another", slug="another", model_number="OLED55G54LW.AEK"
            )
        )
    db_session.add_all([maker, shop, *products])
    db_session.flush()
    if case == "wrong_suffix":
        from app.db.models import ProductModelAlias

        db_session.add(ProductModelAlias(product_id=products[0].id, alias="OLED55G54LW.AEK"))
        db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(ValueError, match="identity"), db_session.begin_nested():
        construct_reference(db_session)
    assert snapshot(db_session) == before


def test_persisted_reward_and_fixed_claim_dates_match_verified_manifest(db_session):
    f = reference_manifest()
    promotion = construct_reference(db_session)
    identity = promotion.id
    db_session.expire_all()
    persisted = db_session.get(Promotion, identity)
    assert persisted.purchase_start_date == date(2025, 5, 21)
    assert persisted.purchase_end_date == date(2025, 6, 24)
    assert persisted.claim_start_date == date(2025, 5, 21)
    assert persisted.claim_end_date == date(2025, 8, 19)
    assert persisted.claim_start_offset_days is None
    assert persisted.claim_end_offset_days is None
    assert persisted.variants[0].retailer_id is not None
    assert len(persisted.source_links) == 2
    assert len({link.source_id for link in persisted.source_links}) == 2
    assert {link.source.source_type for link in persisted.source_links} == {"web_page"}
    assert all(link.source.retrieved_at.tzinfo for link in persisted.source_links)
    claim = next(link.source for link in persisted.source_links if link.role == "claim")
    assert "portal not accessed" in claim.title
    product = db_session.get(Product, persisted.variants[0].product_links[0].product_id)
    assert product.model_number == "OLED55G54LW.AEK"
    benefit = persisted.variants[0].benefits[0]
    assert benefit.benefit_type == f["benefit"]["type"]
    assert benefit.reward.reward_type == f["benefit"]["reward"]["type"]
    assert benefit.reward.fixed_amount == Decimal(f["benefit"]["reward"]["amount_gbp"])


@pytest.mark.parametrize("missing", ["retailer", "product"])
def test_conflicting_existing_reference_cannot_leave_new_rows_after_commit(db_session, missing):
    f = reference_manifest()
    maker = Manufacturer(name="LG", slug="lg")
    caller = Manufacturer(name="Caller maker", slug="caller-maker")
    conflict = Promotion(
        manufacturer=maker,
        name="Conflicting existing reference",
        slug=f["promotion_slug"],
        status=S.REVIEW,
    )
    db_session.add_all([maker, caller, conflict])
    if missing == "product":
        db_session.add(Retailer(name="LG.com/UK", slug="lg-com-uk"))
    db_session.flush()
    caller.name = "Caller change retained"
    db_session.flush()
    before = snapshot(db_session)
    with pytest.raises(ValueError, match="Conflicting existing reference graph"):
        construct_reference(db_session)
    db_session.commit()
    assert snapshot(db_session) == before
    assert db_session.get(Manufacturer, caller.id).name == "Caller change retained"


def test_candidate_failure_cannot_leave_partial_graph_after_caller_commit(db_session, monkeypatch):
    from tests import lg_reference as helper

    caller = Manufacturer(name="Caller maker", slug="caller-maker")
    db_session.add(caller)
    db_session.flush()
    before = snapshot(db_session)

    def fail(candidate):
        # Confirm preflight is reached after a real graph has been flushed.
        assert db_session.scalar(
            select(Promotion).where(Promotion.slug == candidate.promotion.slug)
        )
        raise ValueError("simulated candidate validation failure")

    monkeypatch.setattr(helper, "validate_candidate_promotion", fail)
    with pytest.raises(ValueError, match="simulated"):
        construct_reference(db_session)
    db_session.commit()
    assert snapshot(db_session) == before
    assert db_session.get(Manufacturer, caller.id).name == "Caller maker"


@pytest.mark.parametrize("pending", ["new", "dirty", "deleted"])
def test_pending_caller_changes_are_not_flushed_by_constructor(db_session, pending):
    caller = Manufacturer(name="Caller maker", slug="caller-maker")
    if pending != "new":
        db_session.add(caller)
        db_session.flush()
    before = snapshot(db_session)
    if pending == "new":
        db_session.add(caller)
    elif pending == "dirty":
        caller.name = "Caller changed maker"
    else:
        db_session.delete(caller)
    with pytest.raises(ValueError, match="without pending changes"):
        construct_reference(db_session)
    assert caller in getattr(db_session, pending)
    with db_session.no_autoflush:
        assert snapshot(db_session) == before
    # The caller remains free to commit its own pending work after rejection.
    db_session.commit()
    after = snapshot(db_session)
    assert after != before
    assert all(before[t] == after[t] for t in before.keys() - {"manufacturers"})


@pytest.mark.parametrize("price", [None, Decimal("1.00"), Decimal("2000.00")])
def test_fixed_cashback_independent_of_optional_purchase_price(reference, price):
    result = check(reference[0], date(2025, 6, 24), date(2025, 8, 19), purchase_price=price)
    assert result.promotions[0].benefits[0].cashback_reward_gbp == Decimal("150.00")


@pytest.mark.parametrize(
    "model,retailer,field",
    [
        ("UNKNOWN-LG-MODEL", "LG.com/UK", "model"),
        ("OLED55G54LW", "LG.com/UK", "model"),
        ("OLED55G54LW.AEK", "UNKNOWN-LG-RETAILER", "retailer"),
    ],
)
def test_unknown_identity_and_unreviewed_shortened_model_remain_unresolved(
    reference, model, retailer, field
):
    result = check(reference[0], date(2025, 6, 1), date(2025, 6, 1), model, retailer)
    assert isinstance(result, UnresolvedPurchaseIdentity)
    assert result.field == field
    assert result.status == "not_found"


def test_cleanup_preserves_reused_shared_identity_and_source_rows(db_session):
    maker = Manufacturer(name="LG", slug="lg")
    shop = Retailer(name="LG.com/UK", slug="lg-com-uk")
    product = Product(
        manufacturer=maker,
        name="Shared exact UK TV",
        slug="shared-lg-tv",
        model_number="OLED55G54LW.AEK",
    )
    shared_source = Source(
        url="https://www.lg.com/uk/tncs/g5-cashback/",
        source_type="web_page",
        title="Pre-existing shared source",
        retrieved_at=datetime.fromisoformat(reference_manifest()["evidence"]["retrieved_at"]),
    )
    db_session.add_all([maker, shop, product, shared_source])
    db_session.flush()
    kinds = (Promotion, Source, Product, Retailer, Manufacturer)
    before = {kind: set(db_session.scalars(select(kind.id))) for kind in kinds}
    promotion = construct_reference(db_session)
    assert promotion.manufacturer_id == maker.id
    assert promotion.variants[0].retailer_id == shop.id
    assert promotion.variants[0].product_links[0].product_id == product.id
    owned = {kind: set(db_session.scalars(select(kind.id))) - before[kind] for kind in kinds}
    delete_owned_rows(db_session, owned)
    assert {kind: set(db_session.scalars(select(kind.id))) for kind in kinds} == before
    assert db_session.get(Source, shared_source.id) is shared_source
