import asyncio
import json
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from jsonschema import validate
from sqlalchemy import delete, event, select, text, update
from sqlalchemy.orm import Session

from app.db.models import Benefit, Promotion, PromotionSource, Requirement, Source
from app.mcp import server as adapter
from tests.integration.test_check_purchase import published_graph as published_graph
from tests.integration.test_eligibility_api import body
from tests.integration.test_mcp_check_purchase import mcp_app as mcp_app
from tests.unit.test_mcp_check_purchase import protocol_client

pytestmark = pytest.mark.integration


def error_code(result):
    assert result.is_error and result.structured_content is None
    data = json.loads(result.content[0].text)
    assert set(data) == {"code", "message", "request_id"}
    return data["code"]


def test_real_protocol_parity_read_only_and_cleanup(
    mcp_app, postgres_engine, published_graph, monkeypatch
):
    request, _, variants, product = published_graph
    statements, rollbacks = [], []
    original = adapter.purchase_check_snapshot

    @contextmanager
    def snapshot(*args, **kwargs):
        with original(*args, **kwargs) as pair:
            session = pair[1].session
            assert session.scalar(text("SHOW transaction_read_only")) == "on"
            assert session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            yield pair

    monkeypatch.setattr(adapter, "purchase_check_snapshot", snapshot)

    def record(conn, cursor, statement, params, context, executemany):
        statements.append(statement.split()[0].upper())

    def rollback(conn):
        rollbacks.append(True)

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            tools = (await client.list_tools()).tools
            assert [t.name for t in tools] == ["check_purchase", *adapter.LOOKUP_SCHEMAS]
            checked = (await client.call_tool("check_purchase", body(request))).structured_content
            for promotion in checked["promotions"]:
                variant = promotion["promotion_variant_id"]
                requirements = await client.call_tool(
                    "get_claim_requirements", {"promotion_variant_id": variant}
                )
                validate(requirements.structured_content, tools[2].output_schema)
                data = requirements.structured_content
                assert data["claim_url"] == promotion["provenance"]["claim_url"]
                assert [
                    {k: v for k, v in r.items() if k != "requirement_id"}
                    for r in data["requirements"]
                ] == promotion["requirements"]
                for benefit in promotion["benefits"]:
                    args = {"promotion_variant_id": variant, "benefit_id": benefit["benefit_id"]}
                    result = await client.call_tool("get_benefit", args)
                    validate(result.structured_content, tools[1].output_schema)
                    for field in ("benefit_id", "benefit_type", "name", "description"):
                        assert result.structured_content[field] == benefit[field]
                    if (
                        result.structured_content["reward"]
                        and result.structured_content["reward"]["reward_type"] == "product_specific"
                    ):
                        configured = await client.call_tool(
                            "get_benefit", {**args, "product_id": str(product)}
                        )
                        assert configured.structured_content["reward"]["product_amount_gbp"] == "42"
                for source in promotion["sources"]:
                    result = await client.call_tool(
                        "get_promotion_source",
                        {"promotion_variant_id": variant, "source_id": source["source_id"]},
                    )
                    validate(result.structured_content, tools[3].output_schema)
                    for field, value in source.items():
                        assert result.structured_content[field] == value
                    assert (
                        result.structured_content["last_verified_at"]
                        == promotion["last_verified_at"]
                    )
                    assert postgres_engine.pool.checkedout() == 0
            for variant in (*variants[3:], UUID(int=999)):
                result = await client.call_tool(
                    "get_claim_requirements", {"promotion_variant_id": str(variant)}
                )
                assert error_code(result) == "not_found"
                assert postgres_engine.pool.checkedout() == 0

    event.listen(postgres_engine, "before_cursor_execute", record)
    event.listen(postgres_engine, "rollback", rollback)
    try:
        asyncio.run(run())
        assert not {"INSERT", "UPDATE", "DELETE", "COMMIT"} & set(statements)
        assert len(rollbacks) >= 25
        assert postgres_engine.pool.checkedout() == 0
    finally:
        event.remove(postgres_engine, "before_cursor_execute", record)
        event.remove(postgres_engine, "rollback", rollback)


def test_wrong_benefit_source_links_and_empty_requirements(
    mcp_app, postgres_engine, published_graph
):
    _, promotions, variants, _ = published_graph
    with Session(postgres_engine) as session:
        wrong_benefit = session.scalar(
            select(Benefit.id).where(Benefit.promotion_variant_id == variants[1])
        )
        orphan = Source(
            url="https://example.com/unlinked",
            source_type="web_page",
            retrieved_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        session.add(orphan)
        session.commit()
        source_id = orphan.id
    try:
        with postgres_engine.begin() as connection:
            connection.execute(
                delete(Requirement).where(Requirement.promotion_variant_id == variants[0])
            )

        async def run():
            async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
                for name, field, value in (
                    ("get_benefit", "benefit_id", wrong_benefit),
                    ("get_promotion_source", "source_id", source_id),
                ):
                    result = await client.call_tool(
                        name, {"promotion_variant_id": str(variants[0]), field: str(value)}
                    )
                    assert error_code(result) == "not_found"
                result = await client.call_tool(
                    "get_claim_requirements", {"promotion_variant_id": str(variants[0])}
                )
                assert result.structured_content["requirements"] == []
                assert result.structured_content["requirements_recorded"] is False
                assert postgres_engine.pool.checkedout() == 0

        asyncio.run(run())
    finally:
        with postgres_engine.begin() as connection:
            connection.execute(delete(Source).where(Source.id == source_id))


@pytest.mark.parametrize("role", ["primary", "claim"])
def test_corrupt_provenance_closed_snapshot(mcp_app, postgres_engine, published_graph, role):
    _, promotions, variants, _ = published_graph
    with postgres_engine.begin() as connection:
        connection.execute(
            delete(PromotionSource).where(
                PromotionSource.promotion_id == promotions[0], PromotionSource.role == role
            )
        )

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            result = await client.call_tool(
                "get_claim_requirements", {"promotion_variant_id": str(variants[0])}
            )
            assert error_code(result) == "published_data_invalid"
            assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())


def test_new_snapshot_observes_committed_source_update(mcp_app, postgres_engine, published_graph):
    _, promotions, variants, _ = published_graph
    with Session(postgres_engine) as session:
        source_id = session.scalar(
            select(PromotionSource.source_id).where(
                PromotionSource.promotion_id == promotions[0], PromotionSource.role == "primary"
            )
        )

    async def run():
        args = {"promotion_variant_id": str(variants[0]), "source_id": str(source_id)}
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            first = (await client.call_tool("get_promotion_source", args)).structured_content
            with postgres_engine.begin() as connection:
                connection.execute(
                    update(Source)
                    .where(Source.id == source_id)
                    .values(verified_at=Source.verified_at + timedelta(days=1))
                )
            second = (await client.call_tool("get_promotion_source", args)).structured_content
            assert first["verified_at"] != second["verified_at"]
            assert second["verified_at"] == second["last_verified_at"]
            assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())


@pytest.mark.parametrize("status", ["discovered", "extracted", "review", "archived"])
def test_nonpublished_gate_before_graph_materialization(
    mcp_app, postgres_engine, published_graph, status
):
    _, promotions, variants, _ = published_graph
    with postgres_engine.begin() as connection:
        connection.execute(
            update(Promotion).where(Promotion.id == promotions[0]).values(status=status)
        )
        connection.execute(
            delete(PromotionSource).where(PromotionSource.promotion_id == promotions[0])
        )
    result = mcp_app.state.mcp_server.execute_lookup(
        ("get_claim_requirements", {"promotion_variant_id": str(variants[0])})
    )
    assert error_code(result) == "not_found"
    assert postgres_engine.pool.checkedout() == 0


@pytest.mark.parametrize("failure", ["timeout", "serialization", "sql"])
def test_lookup_failure_releases_connection(
    mcp_app, postgres_engine, published_graph, monkeypatch, failure
):
    from app.mcp.schemas import RequirementsOutput

    _, _, variants, _ = published_graph
    original = adapter.get_published_details

    def failed_query(repository, variant):
        if failure == "timeout":
            repository.session.execute(text("SELECT set_config('statement_timeout', '1ms', true)"))
            repository.session.execute(text("SELECT pg_sleep(30)"))
        elif failure == "sql":
            repository.session.execute(text("SELECT 1 / 0"))
        return original(repository, variant)

    def failed_serialization(*args, **kwargs):
        raise RuntimeError("private serialization data")

    monkeypatch.setattr(adapter, "get_published_details", failed_query)
    if failure == "serialization":
        monkeypatch.setattr(RequirementsOutput, "model_dump", failed_serialization)
    result = mcp_app.state.mcp_server.execute_lookup(
        ("get_claim_requirements", {"promotion_variant_id": str(variants[0])})
    )
    assert error_code(result) == (
        "internal_server_error" if failure == "serialization" else "lookup_unavailable"
    )
    assert "private" not in result.content[0].text
    assert postgres_engine.pool.checkedout() == 0


def test_lookup_mounted_disconnect_closes_snapshot(
    mcp_app, postgres_engine, published_graph, monkeypatch
):
    import threading

    import anyio

    _, _, variants, _ = published_graph
    entered, closed = threading.Event(), threading.Event()
    original_snapshot = adapter.purchase_check_snapshot
    original_lookup = adapter.get_published_details

    @contextmanager
    def tracked_snapshot(*args, **kwargs):
        try:
            with original_snapshot(*args, **kwargs) as pair:
                yield pair
        finally:
            closed.set()

    def blocked(repository, variant):
        entered.set()
        repository.session.execute(text("SELECT pg_sleep(30)"))
        return original_lookup(repository, variant)

    monkeypatch.setattr(adapter, "purchase_check_snapshot", tracked_snapshot)
    monkeypatch.setattr(adapter, "get_published_details", blocked)
    monkeypatch.setattr(adapter, "DB_STATEMENT_TIMEOUT_MS", 250)

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            async with anyio.create_task_group() as tasks:

                async def invoke():
                    await client.call_tool(
                        "get_claim_requirements", {"promotion_variant_id": str(variants[0])}
                    )

                tasks.start_soon(invoke)
                assert await anyio.to_thread.run_sync(entered.wait, 5)
                tasks.cancel_scope.cancel()
            assert await anyio.to_thread.run_sync(closed.wait, 3)
            assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())


def test_invalid_arguments_do_not_checkout_connections(mcp_app, postgres_engine, published_graph):
    checkouts = []

    def checkout(*args):
        checkouts.append(True)

    event.listen(postgres_engine, "checkout", checkout)
    try:
        for arguments in ({}, {"promotion_variant_id": 3}, {"extra": "x" * 8192}):
            result = mcp_app.state.mcp_server.execute_lookup(("get_claim_requirements", arguments))
            assert error_code(result) in {"invalid_lookup_request", "request_too_large"}
        assert checkouts == []
    finally:
        event.remove(postgres_engine, "checkout", checkout)
