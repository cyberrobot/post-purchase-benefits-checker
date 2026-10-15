"""Real MCP/REST/PostgreSQL journeys with explicit scripted purchase extraction."""

import asyncio
from contextlib import contextmanager
from datetime import timedelta

import httpx2
import pytest
from jsonschema import validate
from sqlalchemy import delete, event, text, update

from app.db.models import Promotion, PromotionSource, Requirement
from app.mcp import server as adapter
from tests.chatgpt.flow import (
    Claim,
    Scenario,
    ScriptedConversation,
    assert_grounded,
    safe_error_code,
)
from tests.integration.test_check_purchase import DAY
from tests.integration.test_check_purchase import published_graph as published_graph
from tests.integration.test_eligibility_api import PATH, body
from tests.integration.test_mcp_check_purchase import mcp_app as mcp_app
from tests.unit.test_mcp_check_purchase import protocol_client

pytestmark = pytest.mark.integration


def scenario(request, **changes):
    arguments = {**body(request), **changes}
    if request.purchase_price is None and "purchase_price" not in changes:
        arguments.pop("purchase_price")
    price = arguments.get("purchase_price")
    question = (
        f"I bought {arguments['brand']} {arguments['model']} from "
        f"{arguments['retailer']} on {arguments['purchase_date']}"
        + (f" for £{price}" if price is not None else "")
        + ". Can I claim anything?"
    )
    return Scenario(
        "published-purchase",
        question,
        "call_tool",
        arguments,
        assertion_focus=("classification", "reward", "source"),
        follow_up="What proof is needed, and where does this offer come from?",
    )


def test_independent_answer_claims_grounded_in_protocol_result(
    mcp_app, postgres_engine, published_graph
):
    request, _, variants, _ = published_graph

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            tool = next(t for t in (await client.list_tools()).tools if t.name == "check_purchase")
            result = await client.call_tool("check_purchase", body(request))
            assert not result.is_error
            validate(result.structured_content, tool.output_schema)
            data = result.structured_content
            offer = next(
                p for p in data["promotions"] if p["promotion_variant_id"] == str(variants[0])
            )
            variant_id = offer["promotion_variant_id"]
            benefit_id = next(
                b["benefit_id"] for b in offer["benefits"] if b["benefit_type"] == "cashback"
            )

            # published_graph records an open 29 Feb–30 Mar window, satisfied rules,
            # and a £100 fixed cashback for this variant. Only scopes come from data;
            # answer facts are supplied independently of the returned field values.
            assert_grounded(
                (
                    Claim("classification", "ELIGIBLE", variant_id),
                    Claim(
                        "claim_window",
                        {
                            "status": "open",
                            "opens_on": "2024-02-29",
                            "deadline_on": "2024-03-30",
                        },
                        variant_id,
                    ),
                ),
                data,
            )
            for fabricated in (
                Claim("cashback_reward_gbp", "999.99", variant_id, benefit_id),
                Claim("classification", "NOT_ELIGIBLE", variant_id),
                Claim(
                    "claim_window",
                    {
                        "status": "open",
                        "opens_on": "2024-02-29",
                        "deadline_on": "2099-01-01",
                    },
                    variant_id,
                ),
            ):
                with pytest.raises(AssertionError, match="result grounding"):
                    assert_grounded((fabricated,), data)
            assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())
    assert postgres_engine.pool.checkedout() == 0


@pytest.mark.parametrize(
    "window,expected",
    [
        ("open", "ELIGIBLE"),
        ("missing", "POTENTIALLY_ELIGIBLE"),
        ("future", "CLAIM_NOT_YET_OPEN"),
        ("past", "EXPIRED"),
    ],
)
def test_scripted_question_protocol_parity_grounding_cleanup(
    mcp_app,
    postgres_engine,
    published_graph,
    monkeypatch,
    window,
    expected,
):
    request, promotions, _, _ = published_graph
    values = {
        "missing": {"claim_start_date": None, "claim_end_date": None},
        "future": {
            "claim_start_date": DAY + timedelta(days=1),
            "claim_end_date": DAY + timedelta(days=30),
        },
        "past": {
            "claim_start_date": DAY - timedelta(days=30),
            "claim_end_date": DAY - timedelta(days=1),
        },
    }.get(window)
    if values:
        with postgres_engine.begin() as connection:
            connection.execute(
                update(Promotion).where(Promotion.id == promotions[0]).values(**values)
            )
    case = scenario(
        request,
        **(
            {"purchase_date": (DAY - timedelta(days=1)).isoformat()}
            if window == "purchase-mismatch"
            else {}
        ),
    )
    statements, snapshots = [], []
    original = adapter.purchase_check_snapshot

    @contextmanager
    def observed(*args, **kwargs):
        with original(*args, **kwargs) as pair:
            session = pair[1].session
            assert session.scalar(text("SHOW transaction_read_only")) == "on"
            assert session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            snapshots.append(session)
            yield pair

    monkeypatch.setattr(adapter, "purchase_check_snapshot", observed)

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement.split()[0].upper())

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            tools = (await client.list_tools()).tools
            assert [t.name for t in tools] == [
                "check_purchase",
                "get_benefit",
                "get_claim_requirements",
                "get_promotion_source",
            ]
            for tool in tools:
                assert tool.input_schema["additionalProperties"] is False
                assert tool.output_schema
                assert tool.annotations.read_only_hint and tool.annotations.idempotent_hint
                assert not tool.annotations.destructive_hint
                assert not tool.annotations.open_world_hint
            flow = ScriptedConversation(client, tools)
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=mcp_app), base_url="http://localhost:8000"
            ) as http:
                first = await flow.run(case)
                assert first.failure is None, first.failure
                assert first.calls == [("check_purchase", case.expected_arguments)]
                rest = await http.post(PATH, json=case.expected_arguments)
                assert rest.status_code == 200
                assert first.structured_content == rest.json()
                data = first.structured_content
                assert len(data["promotions"]) == 3
                primary = [p for p in data["promotions"] if p["promotion_id"] == str(promotions[0])]
                assert {p["eligibility"]["classification"] for p in primary} == {expected}
                assert_grounded(first.claims, rest.json())
                repeated = await flow.run(case)
                assert repeated.structured_content == data and repeated.claims == first.claims
                assert postgres_engine.pool.checkedout() == 0
                no_price_request = type(request)(
                    request.brand, request.model, request.retailer, request.purchase_date
                )
                no_price = scenario(no_price_request)
                trace = await flow.run(no_price)
                rest = await http.post(PATH, json=no_price.expected_arguments)
                assert trace.structured_content == rest.json()
                assert trace.submitted_arguments.get("purchase_price") is None
                assert any(
                    b["reward_unavailable_reason"] == "purchase_price_required_for_reward"
                    for p in trace.structured_content["promotions"]
                    for b in p["benefits"]
                )

    event.listen(postgres_engine, "before_cursor_execute", record)
    try:
        asyncio.run(run())
        assert not {"INSERT", "UPDATE", "DELETE", "COMMIT"} & set(statements)
        assert len(snapshots) == 3
        assert postgres_engine.pool.checkedout() == 0
    finally:
        event.remove(postgres_engine, "before_cursor_execute", record)


def test_no_match_unresolved_distinct(mcp_app, published_graph, postgres_engine):
    request, _, _, _ = published_graph

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            flow = ScriptedConversation(client, (await client.list_tools()).tools)
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=mcp_app), base_url="http://localhost:8000"
            ) as http:
                for changes, outcome in [
                    ({"purchase_date": "2020-01-01"}, "resolved"),
                    ({"model": "unknown-synthetic-model"}, "unresolved_identity"),
                ]:
                    case = scenario(request, **changes)
                    trace = await flow.run(case)
                    rest = await http.post(PATH, json=case.expected_arguments)
                    assert trace.structured_content == rest.json()
                    assert trace.structured_content["outcome"] == outcome
                    if outcome == "resolved":
                        assert trace.structured_content["promotions"] == []
                        assert trace.structured_content["no_match_reason"]
                    else:
                        assert trace.structured_content["unresolved_identity"] == {
                            "field": "model",
                            "status": "not_found",
                            "candidate_ids": [],
                        }
                    assert not any(c.kind == "classification" for c in trace.claims)
                    assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())


def test_follow_ups_scoped_without_reclassifying(mcp_app, published_graph, postgres_engine):
    request, _, variants, _ = published_graph
    with postgres_engine.begin() as connection:
        connection.execute(
            delete(Requirement).where(Requirement.promotion_variant_id == variants[0])
        )

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            flow = ScriptedConversation(client, (await client.list_tools()).tools)
            trace = await flow.run(scenario(request))
            original_claims = trace.claims
            for p in trace.structured_content["promotions"]:
                arguments = {"promotion_variant_id": p["promotion_variant_id"]}
                requirements = await flow.detail(trace, "get_claim_requirements", arguments)
                assert requirements["requirements_recorded"] == bool(p["requirements"])
                assert [
                    {k: v for k, v in r.items() if k != "requirement_id"}
                    for r in requirements["requirements"]
                ] == p["requirements"]
                for b in p["benefits"]:
                    detail = await flow.detail(
                        trace, "get_benefit", {**arguments, "benefit_id": b["benefit_id"]}
                    )
                    assert detail["benefit_id"] == b["benefit_id"]
                    assert "eligibility" not in detail and "cashback_reward_gbp" not in detail
                for s in p["sources"]:
                    detail = await flow.detail(
                        trace, "get_promotion_source", {**arguments, "source_id": s["source_id"]}
                    )
                    assert all(detail[k] == v for k, v in s.items())
                    assert detail["last_verified_at"] == p["last_verified_at"]
                assert postgres_engine.pool.checkedout() == 0
            assert trace.claims == original_claims
            first, second = trace.structured_content["promotions"][:2]
            wrong = {
                "promotion_variant_id": first["promotion_variant_id"],
                "benefit_id": second["benefits"][0]["benefit_id"],
            }
            calls = len(trace.calls)
            with pytest.raises(AssertionError, match="unreturned association"):
                await flow.detail(trace, "get_benefit", wrong)
            assert len(trace.calls) == calls
            assert safe_error_code(await client.call_tool("get_benefit", wrong)) == "not_found"
            for variant in variants[3:]:
                invalid = {"promotion_variant_id": str(variant)}
                with pytest.raises(AssertionError, match="unreturned variant"):
                    await flow.detail(trace, "get_claim_requirements", invalid)
                assert (
                    safe_error_code(await client.call_tool("get_claim_requirements", invalid))
                    == "not_found"
                )
            assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"evaluation_date": "2024-02-29"}, "invalid_purchase_request"),
        ({"purchase_date": "2026-02-30"}, "invalid_purchase_request"),
        ({"purchase_price": 42}, "invalid_purchase_request"),
        ({"quantity": 2}, "invalid_purchase_request"),
        ({"model": "x" * 9000}, "request_too_large"),
    ],
)
def test_invalid_proposed_arguments_no_answer(
    mcp_app, published_graph, postgres_engine, changes, code
):
    request, _, _, _ = published_graph

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            flow = ScriptedConversation(client, (await client.list_tools()).tools)
            trace = await flow.run(scenario(request, **changes))
            assert trace.is_error and trace.failure == "backend contract: tool_error"
            assert not trace.claims and trace.structured_content is None
            assert (
                safe_error_code(await client.call_tool("check_purchase", trace.submitted_arguments))
                == code
            )
            assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())


def test_invalid_published_evidence_failure_cleanup(mcp_app, published_graph, postgres_engine):
    request, promotions, _, _ = published_graph
    with postgres_engine.begin() as connection:
        connection.execute(
            delete(PromotionSource).where(
                PromotionSource.promotion_id == promotions[0], PromotionSource.role == "claim"
            )
        )

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            flow = ScriptedConversation(client, (await client.list_tools()).tools)
            for _ in range(2):
                trace = await flow.run(scenario(request))
                assert trace.failure == "backend contract: tool_error"
                assert not trace.claims and trace.structured_content is None
                assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())
