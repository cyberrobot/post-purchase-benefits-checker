"""Offline five-manufacturer acceptance through real PostgreSQL, REST and local MCP.

These tests certify the recorded model only. Hotpoint/Sony remain release-blocked.
"""

import asyncio
from contextlib import contextmanager
from dataclasses import replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import partial
from urllib.parse import urlsplit

import httpx
import httpx2
import pytest
import requests
from jsonschema import validate
from sqlalchemy import event, select, text
from sqlalchemy.orm import sessionmaker

from app.api import eligibility as rest_adapter
from app.application.promotions import PromotionPublicationError, change_promotion_status
from app.application.purchase_check import check_purchase
from app.core.config import Settings
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
    RetailerAlias,
    Source,
)
from app.db.repositories.promotions import promotion_transaction
from app.domain.eligibility_result import EligibilityClassification
from app.domain.promotion_lifecycle import PromotionStatus as S
from app.main import create_app
from app.mcp import server as mcp_adapter
from tests.acceptance.cases import CASES
from tests.chatgpt.flow import (
    Claim,
    Scenario,
    ScriptedConversation,
    assert_grounded,
    safe_error_code,
)
from tests.integration.test_promotion_lifecycle import snapshot
from tests.integration.test_sony_reference_promotion import _ownership_snapshot, delete_owned_rows
from tests.unit.test_mcp_check_purchase import protocol_client
from tests.unit.test_purchase_check import DAY, DETAIL, REQUEST, Repository, Resolver

pytestmark = pytest.mark.integration
PATH = "/api/v1/eligibility/check"
BRANDS = pytest.mark.parametrize("case", CASES, ids=lambda c: c.brand.lower())


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """Block outbound clients, permitting only Docker's local requests transport."""
    original = requests.sessions.Session.request

    def guarded(session, method, url, *args, **kwargs):
        if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1", "localnpipe"}:
            raise AssertionError("acceptance: external HTTP is forbidden")
        return original(session, method, url, *args, **kwargs)

    def forbidden(*args, **kwargs):
        raise AssertionError("acceptance: external HTTP/model calls are forbidden")

    monkeypatch.setattr(requests.sessions.Session, "request", guarded)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", forbidden)
    monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", forbidden)
    monkeypatch.setattr(httpx2.AsyncHTTPTransport, "handle_async_request", forbidden)


@contextmanager
def managed_catalogue(postgres_engine, *, publish=True):
    """Compose once for immutable cases; isolated lifecycle groups own fresh graphs."""
    factory = sessionmaker(postgres_engine)
    with factory() as session:
        before = _ownership_snapshot(session)
        initial = snapshot(session)
    ids = {}
    try:
        with factory.begin() as session:
            for case in CASES:
                promotion = case.helper.construct_reference(session)
                ids[case.brand] = promotion.id
                ids[f"{case.brand}/variant"] = promotion.variants[0].id
                session.add(
                    Product(
                        manufacturer_id=promotion.manufacturer_id,
                        name=f"Synthetic unlinked {case.brand}",
                        slug=f"mvp-unlinked-{case.brand.lower()}",
                        model_number=f"MVP-UNLINKED-{case.brand}",
                    )
                )
                session.flush()
            session.add(Retailer(name="MVP synthetic excluded retailer", slug="mvp-excluded"))
            session.flush()
        operation = partial(promotion_transaction, factory)
        for case in CASES if publish else ():
            change_promotion_status(operation, ids[case.brand], S.ACTIVE)
            if case.brand in {"Samsung", "LG"}:
                change_promotion_status(operation, ids[case.brand], S.EXPIRED)
        yield factory, ids
    finally:
        with factory.begin() as session:
            after = _ownership_snapshot(session)
            delete_owned_rows(session, {kind: after[kind] - before[kind] for kind in before})
            assert snapshot(session) == initial, "fixture: owned graph/aliases must fully clean up"
        assert postgres_engine.pool.checkedout() == 0


@pytest.fixture(scope="class")
def catalogue(postgres_engine, migrated_test_database):
    with managed_catalogue(postgres_engine) as value:
        yield value


@pytest.fixture
def journey(catalogue, postgres_engine, monkeypatch):
    clock = [date(2000, 1, 1)]

    def build_app():
        app = create_app(
            Settings(
                _env_file=None,
                APP_ENV="test",
                MCP_HTTP_ENABLED=True,
                DATABASE_URL="postgresql+psycopg://unused/unused",
            ),
            engine_factory=lambda _: postgres_engine,
        )
        app.dependency_overrides[rest_adapter.uk_evaluation_date] = lambda: clock[0]
        return app

    app = build_app()
    monkeypatch.setattr(mcp_adapter, "uk_evaluation_date", lambda: clock[0])

    @contextmanager
    def observed(original, *args, **kwargs):
        with original(*args, **kwargs) as pair:
            session = pair[1].session
            assert session.scalar(text("SHOW transaction_read_only")) == "on"
            assert session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            yield pair

    for adapter in (rest_adapter, mcp_adapter):
        original = adapter.purchase_check_snapshot
        monkeypatch.setattr(adapter, "purchase_check_snapshot", partial(observed, original))

    async def run(case, inspect, *, arguments=None, evaluation=None):
        clock[0] = date.fromisoformat(evaluation or case.evaluation)
        args = arguments if arguments is not None else case.arguments()
        active_app = build_app()
        async with (
            active_app.router.lifespan_context(active_app),
            protocol_client(active_app) as client,
        ):
            tools = (await client.list_tools()).tools
            tool = next(t for t in tools if t.name == "check_purchase")
            for item in tools:
                assert item.annotations.read_only_hint and item.annotations.idempotent_hint
                assert (
                    not item.annotations.destructive_hint and not item.annotations.open_world_hint
                )
                assert item.input_schema["additionalProperties"] is False
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=active_app), base_url="http://localhost:8000"
            ) as http:
                response = await http.post(PATH, json=args)
                result = await client.call_tool("check_purchase", args)
                assert response.status_code == 200, f"{case.brand}/REST: {response.status_code}"
                assert not result.is_error, f"{case.brand}/MCP: unexpected tool error"
                validate(args, tool.input_schema)
                validate(result.structured_content, tool.output_schema)
                assert result.structured_content == response.json(), f"{case.brand}/REST-MCP parity"
                data = response.json()
                assert data["evaluation_date"] == clock[0].isoformat()
                await inspect(data, client, tools, http)
                assert postgres_engine.pool.checkedout() == 0
                return data

    return app, lambda case, inspect, **kwargs: asyncio.run(run(case, inspect, **kwargs))


async def no_match(data, *_):
    assert data["outcome"] == "resolved"
    assert data["promotions"] == []
    assert data["no_match_reason"] == "no_matching_published_promotions"
    assert data["resolved_identity"]


def offer(data, case, ids, classification="ELIGIBLE", reason="claim_window_open"):
    assert data["outcome"] == "resolved", f"{case.brand}/service outcome"
    assert len(data["promotions"]) == 1, f"{case.brand}/candidate isolation"
    result = data["promotions"][0]
    assert result["promotion_id"] == str(ids[case.brand])
    assert result["promotion_variant_id"] == str(ids[f"{case.brand}/variant"])
    assert result["eligibility"]["classification"] == classification, case.brand
    assert [r["code"] for r in result["eligibility"]["reasons"]] == [
        "all_configured_rules_satisfied",
        reason,
    ]
    assert result["eligibility"]["rule_evaluations"] == [
        {"kind": kind, "status": "satisfied", "reason_code": f"{kind}_match"}
        for kind in ("manufacturer", "product", "retailer", "purchase_date")
    ]
    assert len(result["benefits"]) == 1
    assert result["benefits"][0]["cashback_reward_gbp"] == case.reward
    assert result["benefits"][0]["reward_unavailable_reason"] is None
    manifest = case.manifest
    assert {r["requirement_type"] for r in result["requirements"]} == {
        r["type"] for r in manifest["requirements"]
    }
    assert {r["requirement_type"]: r["description"] for r in result["requirements"]} == {
        r["type"]: r["description"] for r in manifest["requirements"]
    }
    assert result["provenance"]["official_source_url"] == manifest["official_terms_url"]
    assert result["provenance"]["claim_url"] == manifest["claim_url"]
    assert datetime.fromisoformat(result["last_verified_at"]) == datetime.fromisoformat(
        manifest["evidence"]["verified_at"]
    )
    assert result["last_verified_at"] == result["provenance"]["verified_at"]
    sources = {s["role"]: s for s in result["sources"]}
    assert sources["primary"]["url"] == manifest["official_terms_url"]
    assert sources["claim"]["url"] == manifest["claim_url"]
    assert sources["primary"]["source_type"] == (
        "pdf" if case.brand in {"Samsung", "Sony"} else "web_page"
    )
    assert sources["claim"]["source_type"] == "web_page"
    for role in ("primary", "claim"):
        assert datetime.fromisoformat(sources[role]["verified_at"]) == datetime.fromisoformat(
            manifest["evidence"]["verified_at"]
        )
        assert datetime.fromisoformat(sources[role]["retrieved_at"]) == datetime.fromisoformat(
            manifest["evidence"]["retrieved_at"]
        )
    expected_supporting = {
        "Samsung": manifest.get("samsung_newsroom_url"),
        "Sony": manifest.get("dealer_list_url"),
    }.get(case.brand)
    assert set(sources) == (
        {"primary", "claim", "supporting"} if expected_supporting else {"primary", "claim"}
    )
    if expected_supporting:
        assert sources["supporting"]["url"] == expected_supporting
    assert result["explanation"][0] == "The recorded eligibility rules match this purchase."
    return result


async def followups(data, client, tools, _http):
    original = repr(data)
    for result in data["promotions"]:
        args = {"promotion_variant_id": result["promotion_variant_id"]}
        requirements = await client.call_tool("get_claim_requirements", args)
        assert not requirements.is_error
        detail = requirements.structured_content
        validate(detail, next(t.output_schema for t in tools if t.name == "get_claim_requirements"))
        assert detail["promotion_variant_id"] == args["promotion_variant_id"]
        assert [
            {k: v for k, v in r.items() if k != "requirement_id"} for r in detail["requirements"]
        ] == result["requirements"]
        for benefit in result["benefits"]:
            response = await client.call_tool(
                "get_benefit", {**args, "benefit_id": benefit["benefit_id"]}
            )
            assert not response.is_error
            detail = response.structured_content
            validate(
                detail,
                next(t.output_schema for t in tools if t.name == "get_benefit"),
            )
            assert detail["promotion_id"] == result["promotion_id"]
            assert detail["promotion_variant_id"] == args["promotion_variant_id"]
            assert detail["benefit_id"] == benefit["benefit_id"]
            assert detail["benefit_type"] == benefit["benefit_type"]
            reward = detail["reward"]
            assert reward is not None
            assert reward["reward_type"] == "fixed_amount"
            assert Decimal(reward["fixed_amount_gbp"]) == Decimal(benefit["cashback_reward_gbp"])
            assert "eligibility" not in detail
        for source in result["sources"]:
            response = await client.call_tool(
                "get_promotion_source", {**args, "source_id": source["source_id"]}
            )
            assert not response.is_error
            detail = response.structured_content
            assert detail["promotion_variant_id"] == args["promotion_variant_id"]
            assert all(detail[k] == v for k, v in source.items())
            assert detail["last_verified_at"] == result["last_verified_at"]
        assert_grounded(
            (
                Claim(
                    "classification",
                    result["eligibility"]["classification"],
                    result["promotion_variant_id"],
                ),
            ),
            data,
        )
    assert repr(data) == original


class TestMVPAcceptance:
    def test_mvp_five_manufacturer_catalogue_loaded_and_scoped(self, catalogue, journey):
        factory, ids = catalogue
        with factory() as session:
            before = snapshot(session)
            for case in CASES:
                assert case.helper.construct_reference(session).id == ids[case.brand]
            assert snapshot(session) == before
            hisense, sony = (session.get(Promotion, ids[b]) for b in ("Hisense", "Sony"))
            assert hisense.variants[0].retailer_id == sony.variants[0].retailer_id
            assert session.get(RetailerAlias, (sony.variants[0].retailer_id, "currys - uk"))
        for case in CASES:

            async def inspect(data, *_, case=case):
                offer(data, case, ids)

            journey[1](case, inspect)

    @BRANDS
    def test_mvp_positive_rest_mcp_parity(self, case, catalogue, journey):
        async def inspect(data, client, tools, http):
            result = offer(data, case, catalogue[1])
            assert result["claim_window"] == {
                "status": "open",
                "opens_on": case.opens,
                "deadline_on": case.deadline,
            }
            assert result["promotion_status"] == (
                "expired" if case.brand in {"Samsung", "LG"} else "active"
            )
            flow = ScriptedConversation(client, tools)
            trace = await flow.run(
                Scenario(
                    f"{case.brand}-positive",
                    "Synthetic complete purchase",
                    "call_tool",
                    case.arguments(),
                )
            )
            assert trace.structured_content == data and trace.failure is None
            assert trace.calls == [("check_purchase", case.arguments())]

        journey[1](case, inspect)

    @BRANDS
    def test_mvp_supporting_tools_ground_evidence(self, case, catalogue, journey):
        async def inspect(data, client, tools, http):
            offer(data, case, catalogue[1])
            await followups(data, client, tools, http)
            repeated = await client.call_tool("check_purchase", case.arguments())
            assert not repeated.is_error and repeated.structured_content == data

        journey[1](case, inspect)

    @BRANDS
    @pytest.mark.parametrize("scenario", ("before_start", "after_end", "unlinked_model"))
    def test_mvp_negative_purchase_boundaries_and_models(self, case, scenario, journey):
        manifest = case.manifest
        changes = {
            "before_start": {
                "purchase_date": (
                    date.fromisoformat(manifest["purchase_start_date"]) - timedelta(days=1)
                ).isoformat()
            },
            "after_end": {
                "purchase_date": (
                    date.fromisoformat(manifest["purchase_end_date"]) + timedelta(days=1)
                ).isoformat()
            },
            "unlinked_model": {"model": f"MVP-UNLINKED-{case.brand}"},
        }[scenario]
        journey[1](case, no_match, arguments=case.arguments(**changes))

    @BRANDS
    def test_mvp_retailer_restrictions_are_not_false_matches(self, case, journey):
        journey[1](
            case, no_match, arguments=case.arguments(retailer="MVP synthetic excluded retailer")
        )

    @BRANDS
    def test_mvp_expired_and_not_yet_open_claim_windows(self, case, catalogue, journey):
        async def expired(data, *_):
            result = offer(data, case, catalogue[1], "EXPIRED", "claim_window_expired")
            assert result["claim_window"]["status"] == "expired"
            assert result["claim_window"]["deadline_on"] == (
                "2026-07-22" if case.brand == "Samsung" else case.deadline
            )

        journey[1](
            case,
            expired,
            arguments=case.arguments(purchase_date=case.expired_purchase),
            evaluation=case.expired_evaluation,
        )
        if case.not_yet_open is not None:

            async def future(data, *_):
                result = offer(
                    data, case, catalogue[1], "CLAIM_NOT_YET_OPEN", "claim_window_not_yet_open"
                )
                assert result["claim_window"]["opens_on"] == case.opens

            journey[1](case, future, evaluation=case.not_yet_open)
        else:
            assert case.brand in {"Samsung", "LG"}  # N/A: no valid post-purchase closed opening

    @BRANDS
    def test_mvp_missing_and_unresolved_purchase_details(
        self, case, journey, postgres_engine, monkeypatch
    ):
        app = journey[0]

        async def run():
            async with app.router.lifespan_context(app), protocol_client(app) as client:
                tools = (await client.list_tools()).tools
                flow = ScriptedConversation(client, tools)
                async with httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=app), base_url="http://localhost:8000"
                ) as http:
                    invalid = []
                    for field in ("brand", "model", "retailer", "purchase_date"):
                        args = case.arguments()
                        del args[field]
                        invalid.append(args)
                        trace = await flow.run(
                            Scenario(
                                f"{case.brand}-missing-{field}",
                                "Incomplete synthetic purchase",
                                "ask_for_missing_details",
                                expected_missing_fields=(field,),
                            )
                        )
                        assert trace.missing_fields == (field,) and trace.calls == []
                        assert trace.structured_content is None
                    invalid.extend(
                        [
                            case.arguments(purchase_date="2026-02-30"),
                            case.arguments(purchase_price=100),
                            case.arguments(purchase_price="-1.00"),
                            case.arguments(purchase_price="not-money"),
                            case.arguments(model=""),
                            case.arguments(brand=None),
                            case.arguments(extra="unexpected"),
                        ]
                    )
                    for args in invalid:
                        response = await http.post(PATH, json=args)
                        assert response.status_code == 422
                        assert response.headers["content-type"].startswith(
                            "application/problem+json"
                        )
                        assert response.headers["x-request-id"]
                        assert response.json()["code"] == "invalid_purchase_request"
                        result = await client.call_tool("check_purchase", args)
                        assert result.is_error and result.structured_content is None
                        assert "promotions" not in response.json()
                        assert postgres_engine.pool.checkedout() == 0

        def forbidden_service(*args, **kwargs):
            raise AssertionError("validation: malformed input must not call purchase service")

        with monkeypatch.context() as boundary:
            boundary.setattr(rest_adapter, "check_purchase", forbidden_service)
            boundary.setattr(mcp_adapter, "check_purchase", forbidden_service)
            asyncio.run(run())
        for field in ("brand", "model", "retailer"):

            async def unresolved(data, *_, field=field):
                assert data["outcome"] == "unresolved_identity"
                assert data["unresolved_identity"] == {
                    "field": field,
                    "status": "not_found",
                    "candidate_ids": [],
                }
                assert "promotions" not in data

            journey[1](
                case, unresolved, arguments=case.arguments(**{field: "MVP unknown identity"})
            )

        # Price variants compare the complete persisted answer; expected amount is independent.
        async def price(data, *_):
            assert data["promotions"][0]["benefits"][0]["cashback_reward_gbp"] == case.reward
            assert data["promotions"][0]["eligibility"]["classification"] == "ELIGIBLE"

        omitted = journey[1](case, price)
        supplied = journey[1](case, price, arguments=case.arguments(purchase_price="999.99"))
        assert omitted == supplied

    def test_mvp_repeated_checks_are_read_only_and_fixture_cleanup_safe(
        self, catalogue, journey, postgres_engine
    ):
        factory, ids = catalogue
        with factory() as session:
            before = snapshot(session)
        statements = []

        def record(_conn, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.strip().split()[0].upper())

        event.listen(postgres_engine, "before_cursor_execute", record)
        try:
            for case in CASES:

                async def inspect(data, *_, case=case):
                    offer(data, case, ids)

                assert journey[1](case, inspect) == journey[1](case, inspect)
            assert not {"INSERT", "UPDATE", "DELETE", "COMMIT"} & set(statements)
        finally:
            event.remove(postgres_engine, "before_cursor_execute", record)
        with factory() as session:
            assert snapshot(session) == before
        assert postgres_engine.pool.checkedout() == 0

    @pytest.mark.parametrize(
        "brand,purchase,evaluation,earliest,wait",
        [
            ("Hotpoint", "2026-06-12", "2026-06-13", "2026-07-12", 30),
            ("Sony", "2026-10-27", "2026-11-04", "2026-12-01", 35),
        ],
    )
    def test_mvp_individual_wait_prevents_premature_claim_readiness(
        self, brand, purchase, evaluation, earliest, wait, catalogue, journey, record_property
    ):
        case = next(c for c in CASES if c.brand == brand)
        # Original evidence-capture observations predate typed support. Their historical
        # flags are preserved evidence, not current publication or runtime gates.
        original_capture_observation = case.manifest["claim_delay_limitation"]
        current_claim_window = case.manifest["claim_window"]
        assert original_capture_observation["status"] == "unmodelled"
        assert original_capture_observation["production_publication_permitted"] is False
        assert original_capture_observation["authoritative_runtime_rule"] is False
        assert original_capture_observation["minimum_days_after_purchase"] == wait
        assert current_claim_window["minimum_days_after_purchase"] == wait
        assert (
            original_capture_observation["minimum_days_after_purchase"]
            == current_claim_window["minimum_days_after_purchase"]
        )
        purchased_on = date.fromisoformat(purchase)
        evaluated_on = date.fromisoformat(evaluation)
        earliest_on = date.fromisoformat(earliest)
        assert purchased_on < evaluated_on < earliest_on
        assert earliest_on == purchased_on + timedelta(days=wait)
        fixed_window = current_claim_window
        assert fixed_window["type"] == "fixed"
        assert (
            date.fromisoformat(fixed_window["start_date"])
            <= evaluated_on
            <= date.fromisoformat(fixed_window["end_date"])
        )

        async def diagnostic(data, *_):
            # P0: the pinned official waiting periods below outrank the broad fixed window.
            # Both the campaign window and the individual waiting period must be enforced.
            observed = data["promotions"][0]
            eligibility = observed["eligibility"]
            assert eligibility["classification"] == "CLAIM_NOT_YET_OPEN", (
                f"P0 release blocker: {brand} cannot be claim-ready on {evaluation}; "
                f"individual opening is {earliest} ({wait} days after purchase)"
            )
            assert "claim_window_not_yet_open" in {
                reason["code"] for reason in eligibility["reasons"]
            }
            assert observed["claim_window"]["opens_on"] == earliest

        journey[1](
            case,
            diagnostic,
            arguments=case.arguments(purchase_date=purchase),
            evaluation=evaluation,
        )
        historically_unmodelled_brands = [
            c.brand
            for c in CASES
            if c.manifest.get("claim_delay_limitation", {}).get("production_publication_permitted")
            is False
        ]
        assert historically_unmodelled_brands == ["Hotpoint", "Sony"]
        record_property(
            "represented_wait_rule",
            f"VERIFIED: {brand} individual {wait}-day wait only; "
            "other claimant restrictions and production approval remain unverified",
        )


def test_mvp_historical_published_promotions_remain_available(catalogue, journey):
    factory, ids = catalogue
    operation = partial(promotion_transaction, factory)
    for case in CASES:
        before = journey[1](case, followups)
        if case.brand not in {"Samsung", "LG"}:
            change_promotion_status(operation, ids[case.brand], S.EXPIRED)

        async def historic(data, client, tools, http, case=case, before=before):
            result = offer(data, case, ids)
            assert result["promotion_status"] == "expired"
            prior = before["promotions"][0]
            for field in (
                "promotion_variant_id",
                "benefits",
                "requirements",
                "sources",
                "provenance",
                "last_verified_at",
            ):
                assert result[field] == prior[field]
            await followups(data, client, tools, http)

        journey[1](case, historic)

        async def closed(data, client, tools, http, case=case):
            result = offer(data, case, ids, "EXPIRED", "claim_window_expired")
            assert result["promotion_status"] == "expired"
            await followups(data, client, tools, http)

        journey[1](
            case,
            closed,
            arguments=case.arguments(purchase_date=case.expired_purchase),
            evaluation=case.expired_evaluation,
        )


def test_mvp_unpublished_and_invalid_publication_never_surface(
    postgres_engine, migrated_test_database, monkeypatch
):
    # A separate fresh five-brand graph avoids changing the immutable catalogue.
    with managed_catalogue(postgres_engine, publish=False) as unpublished:
        factory, ids = unpublished

        async def check_all():
            app = create_app(
                Settings(
                    _env_file=None,
                    APP_ENV="test",
                    MCP_HTTP_ENABLED=True,
                    DATABASE_URL="postgresql+psycopg://unused/unused",
                ),
                engine_factory=lambda _: postgres_engine,
            )
            async with app.router.lifespan_context(app), protocol_client(app) as client:
                async with httpx2.AsyncClient(
                    transport=httpx2.ASGITransport(app=app), base_url="http://localhost:8000"
                ) as http:
                    for case in CASES:
                        app.dependency_overrides[rest_adapter.uk_evaluation_date] = (
                            lambda case=case: date.fromisoformat(case.evaluation)
                        )
                        monkeypatch.setattr(
                            mcp_adapter,
                            "uk_evaluation_date",
                            lambda case=case: date.fromisoformat(case.evaluation),
                        )
                        rest = await http.post(PATH, json=case.arguments())
                        result = await client.call_tool("check_purchase", case.arguments())
                        assert rest.status_code == 200 and not result.is_error
                        assert result.structured_content == rest.json()
                        await no_match(rest.json())

        asyncio.run(check_all())
        for case in CASES:
            with factory.begin() as session:
                promotion = session.get(Promotion, ids[case.brand])
                source = next(
                    link.source for link in promotion.source_links if link.role == "primary"
                )
                source.verified_at = None
            with factory() as session:
                before = snapshot(session)
            with pytest.raises(PromotionPublicationError):
                change_promotion_status(
                    partial(promotion_transaction, factory), ids[case.brand], S.ACTIVE
                )
            with factory() as session:
                assert session.get(Promotion, ids[case.brand]).status == S.REVIEW
                assert snapshot(session) == before
        asyncio.run(check_all())
        for case in CASES:
            change_promotion_status(
                partial(promotion_transaction, factory), ids[case.brand], S.ARCHIVED
            )
        asyncio.run(check_all())
        assert postgres_engine.pool.checkedout() == 0


def test_mvp_ambiguous_curated_alias_is_not_a_negative(catalogue, journey):
    factory, _ = catalogue
    with factory.begin() as session:
        shops = list(session.scalars(select(Retailer).where(Retailer.name.in_(["Currys", "Wren"]))))
        assert len(shops) == 2
        for shop in shops:
            session.add(RetailerAlias(retailer_id=shop.id, alias="MVP ambiguous curated alias"))
        shop_ids = {str(shop.id) for shop in shops}
    case = CASES[2]

    async def ambiguous(data, *_):
        assert data["outcome"] == "unresolved_identity"
        value = data["unresolved_identity"]
        assert value["field"] == "retailer" and value["status"] == "ambiguous"
        assert set(value["candidate_ids"]) == shop_ids
        assert "promotions" not in data

    journey[1](case, ambiguous, arguments=case.arguments(retailer="MVP ambiguous curated alias"))


def test_mvp_corrupt_published_data_fails_safely(catalogue, journey, postgres_engine):
    factory, ids = catalogue
    case = CASES[0]
    with factory.begin() as session:
        promotion = session.get(Promotion, ids[case.brand])
        session.delete(next(link for link in promotion.source_links if link.role == "claim"))
    app = journey[0]

    async def run():
        async with app.router.lifespan_context(app), protocol_client(app) as client:
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://localhost:8000"
            ) as http:
                for _ in range(2):
                    rest = await http.post(PATH, json=case.arguments())
                    assert rest.status_code == 500
                    assert rest.headers["x-request-id"]
                    assert rest.headers["content-type"].startswith("application/problem+json")
                    assert rest.json()["code"] == "published_data_invalid"
                    result = await client.call_tool("check_purchase", case.arguments())
                    assert safe_error_code(result) == "published_data_invalid"
                    assert result.structured_content is None
                    for forbidden in ("SELECT", "Traceback", "postgresql", "/Users/", "password"):
                        assert forbidden not in rest.text
                        assert forbidden not in " ".join(c.text for c in result.content)
                    assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())


def test_mvp_missing_claim_window_application_contract_seam():
    """Acceptance at the application seam only: no persisted publication or transports.

    Reuse the synthetic service fixtures, independently of all five manufacturer
    references. The separate PostgreSQL test proves this cannot be published.
    """
    detail = replace(DETAIL, claim_start_date=None, claim_end_date=None)

    def evaluate():
        return check_purchase(
            REQUEST,
            evaluation_date=DAY,
            identity_resolver=Resolver(),
            promotion_repository=Repository((detail,)),
        )

    result = evaluate()
    assert evaluate() == result
    assert len(result.promotions) == 1
    observed = result.promotions[0]
    assert observed.eligibility.classification == EligibilityClassification.POTENTIALLY_ELIGIBLE
    assert [reason.code.value for reason in observed.eligibility.reasons] == [
        "all_configured_rules_satisfied",
        "claim_window_unspecified",
    ]
    assert observed.claim_window is None
    assert observed.explanation == (
        "The recorded eligibility rules match this purchase.",
        "The claim period is not available.",
    )


def test_mvp_missing_claim_window_synthetic_cannot_bypass_publication(catalogue, journey):
    factory, _ = catalogue
    # An independent synthetic graph carries no facts or evidence from real offers.
    with factory.begin() as session:
        maker = Manufacturer(name="MVP Synthetic Maker", slug="mvp-synthetic-maker")
        shop = Retailer(name="MVP Synthetic Shop", slug="mvp-synthetic-shop")
        product = Product(
            manufacturer=maker,
            name="MVP Synthetic Product",
            slug="mvp-synthetic-product",
            model_number="MVP-SYNTHETIC",
        )
        session.add_all([maker, shop, product])
        session.flush()
        synthetic = Promotion(
            manufacturer_id=maker.id,
            name="Synthetic unspecified-window acceptance fixture",
            slug="mvp-synthetic-unspecified-window",
            status=S.REVIEW,
            purchase_start_date=date(2000, 1, 1),
            purchase_end_date=date(2000, 1, 1),
        )
        session.add(synthetic)
        session.flush()
        variant = PromotionVariant(
            promotion_id=synthetic.id,
            retailer_id=shop.id,
            code="synthetic",
            name="Synthetic unspecified window",
        )
        session.add(variant)
        session.flush()
        session.add(PromotionVariantProduct(promotion_variant_id=variant.id, product_id=product.id))
        benefit = Benefit(
            promotion_variant_id=variant.id, benefit_type="cashback", name="Synthetic fixed reward"
        )
        session.add(benefit)
        session.flush()
        from decimal import Decimal

        session.add(
            BenefitReward(
                benefit_id=benefit.id, reward_type="fixed_amount", fixed_amount=Decimal("1.00")
            )
        )
        for role in ("primary", "claim"):
            source = Source(
                url=f"https://example.test/mvp-synthetic/{role}",
                source_type="web_page",
                retrieved_at=datetime.fromisoformat("2000-01-01T00:00:00Z"),
                verified_at=datetime.fromisoformat("2000-01-01T00:00:00Z"),
            )
            session.add(source)
            session.flush()
            session.add(PromotionSource(promotion_id=synthetic.id, source_id=source.id, role=role))
        synthetic_id = synthetic.id
    with factory() as session:
        before = snapshot(session)
    with pytest.raises(PromotionPublicationError) as error:
        change_promotion_status(partial(promotion_transaction, factory), synthetic_id, S.ACTIVE)
    assert {issue.code for issue in error.value.report.issues} == {"missing_claim_window"}
    with factory() as session:
        assert snapshot(session) == before
        assert session.get(Promotion, synthetic_id).status == S.REVIEW
    # The runtime supports unknown windows, but the current publication gate cannot
    # create this configuration. Do not fake a published row to satisfy the matrix.
    journey[1](
        CASES[0],
        no_match,
        arguments=CASES[0].arguments(
            brand="MVP Synthetic Maker",
            model="MVP-SYNTHETIC",
            retailer="MVP Synthetic Shop",
            purchase_date="2000-01-01",
        ),
        evaluation="2000-01-01",
    )
