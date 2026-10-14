import asyncio
from contextlib import contextmanager

import httpx2
import pytest
from jsonschema import validate
from sqlalchemy import delete, event, text

from app.api.eligibility import uk_evaluation_date
from app.core.config import Settings
from app.db.models import PromotionSource
from app.main import create_app
from app.mcp import server as adapter
from tests.integration.test_check_purchase import DAY
from tests.integration.test_check_purchase import published_graph as published_graph
from tests.integration.test_eligibility_api import PATH, body
from tests.unit.test_mcp_check_purchase import protocol_client

pytestmark = pytest.mark.integration


@pytest.fixture
def mcp_app(postgres_engine, published_graph, monkeypatch):
    app = create_app(
        Settings(
            _env_file=None,
            APP_ENV="test",
            DATABASE_URL="postgresql+psycopg://unused/unused",
            MCP_HTTP_ENABLED=True,
        ),
        engine_factory=lambda _: postgres_engine,
    )
    app.dependency_overrides[uk_evaluation_date] = lambda: DAY
    monkeypatch.setattr(adapter, "uk_evaluation_date", lambda: DAY)
    return app


@pytest.mark.parametrize("mode", ["legacy", "2026-07-28"])
def test_protocol_rest_full_parity_snapshot_and_cleanup(
    mcp_app, postgres_engine, published_graph, mode, monkeypatch
):
    request, _, variants, _ = published_graph
    statements, rollbacks, sessions = [], [], []
    original = adapter.purchase_check_snapshot

    @contextmanager
    def observed(factory, **kwargs):
        with original(factory, **kwargs) as (resolver, repository):
            assert (
                repository.session.scalar(text("SHOW transaction_isolation")) == "repeatable read"
            )
            assert repository.session.scalar(text("SHOW transaction_read_only")) == "on"
            sessions.append(repository.session)
            yield resolver, repository

    monkeypatch.setattr(adapter, "purchase_check_snapshot", observed)

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip().split()[0].upper())

    def rollback(connection):
        rollbacks.append(True)

    async def run():
        async with (
            mcp_app.router.lifespan_context(mcp_app),
            protocol_client(mcp_app, mode) as client,
        ):
            tools = await client.list_tools()
            assert [t.name for t in tools.tools] == ["check_purchase"]
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=mcp_app), base_url="http://localhost:8000"
            ) as http:
                assert (await http.get("/health")).status_code == 200
                for changes in (
                    {},
                    {"purchase_price": "0.00"},
                    {"purchase_price": None},
                    {"model": "missing"},
                    {"purchase_date": "2020-01-01"},
                ):
                    arguments = {**body(request), **changes}
                    rest = await http.post(PATH, json=arguments)
                    assert rest.status_code == 200
                    result = await client.call_tool("check_purchase", arguments)
                    assert not result.is_error
                    assert result.structured_content == rest.json()
                    validate(result.structured_content, tools.tools[0].output_schema)
                    assert postgres_engine.pool.checkedout() == 0
                    if not changes:
                        data = result.structured_content
                        assert len(data["promotions"]) == 3
                        assert {p["promotion_variant_id"] for p in data["promotions"]} == set(
                            map(str, variants[:3])
                        )
                        assert {p["promotion_status"] for p in data["promotions"]} == {
                            "active",
                            "expired",
                        }
                        assert all(
                            p["last_verified_at"] == p["provenance"]["verified_at"]
                            for p in data["promotions"]
                        )

    event.listen(postgres_engine, "before_cursor_execute", record)
    event.listen(postgres_engine, "rollback", rollback)
    try:
        asyncio.run(run())
        assert not ({"INSERT", "UPDATE", "DELETE", "COMMIT"} & set(statements))
        assert len(rollbacks) == 10
        assert len(sessions) == len({id(s) for s in sessions}) == 5
        assert postgres_engine.pool.checkedout() == 0
    finally:
        event.remove(postgres_engine, "before_cursor_execute", record)
        event.remove(postgres_engine, "rollback", rollback)


def test_invalid_published_graph_protocol_error_closes_snapshot(
    mcp_app, postgres_engine, published_graph
):
    import json

    request, promotions, _, _ = published_graph
    with postgres_engine.begin() as connection:
        connection.execute(
            delete(PromotionSource).where(
                PromotionSource.promotion_id == promotions[0], PromotionSource.role == "claim"
            )
        )

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            for _ in range(2):
                result = await client.call_tool("check_purchase", body(request))
                assert result.is_error and result.structured_content is None
                assert json.loads(result.content[0].text)["code"] == "published_data_invalid"
                assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())


def test_cancelled_call_releases_postgres_snapshot(
    mcp_app, postgres_engine, published_graph, monkeypatch
):
    import threading

    import anyio

    request, _, _, _ = published_graph
    entered, signalled = threading.Event(), threading.Event()
    original = adapter.check_purchase
    original_snapshot = adapter.purchase_check_snapshot
    events = []

    @contextmanager
    def tracked_snapshot(*args, **kwargs):
        events.append(kwargs["cancellation_event"])
        with original_snapshot(*args, **kwargs) as pair:
            yield pair

    def blocked(*args, **kwargs):
        entered.set()
        assert events[0].wait(timeout=5)
        signalled.set()
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "check_purchase", blocked)
    monkeypatch.setattr(adapter, "purchase_check_snapshot", tracked_snapshot)

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app):
            async with anyio.create_task_group() as tasks:
                tasks.start_soon(
                    mcp_app.state.mcp_server.call_tool, "check_purchase", body(request)
                )
                assert await anyio.to_thread.run_sync(entered.wait, 5)
                assert postgres_engine.pool.checkedout() == 1
                tasks.cancel_scope.cancel()

            assert signalled.is_set()
            assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())


def test_cooperative_cancellation_prevents_later_postgres_queries(
    mcp_app, postgres_engine, published_graph, monkeypatch
):
    import threading

    from sqlalchemy import text

    request, _, _, _ = published_graph
    cancellation = threading.Event()
    statements = []

    def cancel_between_queries(*args, **kwargs):
        session = kwargs["promotion_repository"].session
        session.execute(text("SELECT 1"))
        cancellation.set()
        session.execute(text("SELECT 2"))

    def record(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.strip())

    monkeypatch.setattr(adapter, "check_purchase", cancel_between_queries)
    event.listen(postgres_engine, "before_cursor_execute", record)
    try:
        result = mcp_app.state.mcp_server.execute(body(request), cancellation)
        assert result.is_error and result.structured_content is None
        assert any(statement == "SELECT 1" for statement in statements)
        assert not any(statement == "SELECT 2" for statement in statements)
        assert postgres_engine.pool.checkedout() == 0
    finally:
        event.remove(postgres_engine, "before_cursor_execute", record)


def test_mounted_protocol_disconnect_bounds_query_and_closes_snapshot(
    mcp_app, postgres_engine, published_graph, monkeypatch
):
    import threading

    import anyio
    from sqlalchemy import text

    request, _, _, _ = published_graph
    entered, closed = threading.Event(), threading.Event()
    original_snapshot = adapter.purchase_check_snapshot
    original_check = adapter.check_purchase

    @contextmanager
    def tracked_snapshot(*args, **kwargs):
        try:
            with original_snapshot(*args, **kwargs) as snapshot:
                yield snapshot
        finally:
            closed.set()

    def blocked_by_database(*args, **kwargs):
        entered.set()
        repository = kwargs["promotion_repository"]
        repository.session.execute(text("SELECT pg_sleep(30)"))
        return original_check(*args, **kwargs)

    monkeypatch.setattr(adapter, "purchase_check_snapshot", tracked_snapshot)
    monkeypatch.setattr(adapter, "check_purchase", blocked_by_database)
    monkeypatch.setattr(adapter, "DB_STATEMENT_TIMEOUT_MS", 250)

    async def run():
        async with mcp_app.router.lifespan_context(mcp_app), protocol_client(mcp_app) as client:
            async with anyio.create_task_group() as tasks:

                async def invoke():
                    await client.call_tool("check_purchase", body(request))

                tasks.start_soon(invoke)
                assert await anyio.to_thread.run_sync(entered.wait, 5)
                assert postgres_engine.pool.checkedout() == 1
                tasks.cancel_scope.cancel()
            assert await anyio.to_thread.run_sync(closed.wait, 3)
            assert postgres_engine.pool.checkedout() == 0

    asyncio.run(run())
