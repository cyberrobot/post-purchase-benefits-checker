import asyncio
import json
from contextlib import asynccontextmanager, contextmanager
from unittest.mock import Mock
from uuid import UUID

import httpx2
import pytest
from jsonschema import validate
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api.schemas.eligibility import map_result
from app.application.identity_matching import IdentityPersistenceError
from app.application.promotion_candidate_matching import UnresolvedPurchaseIdentity
from app.application.promotions import PromotionPersistenceError
from app.application.purchase_check_details import CheckPurchaseResult, PublishedPromotionDataError
from app.core.config import Settings
from app.domain.identity_normalisation import MatchStatus
from app.main import create_app
from app.mcp import server as adapter
from tests.unit.test_eligibility_api import BODY, DAY, IDENTITY, offer


@asynccontextmanager
async def protocol_client(app, mode="legacy", peer=("127.0.0.1", 12345)):
    async with httpx2.AsyncClient(transport=httpx2.ASGITransport(app=app, client=peer)) as http:
        transport = streamable_http_client("http://localhost:8000/mcp", http_client=http)
        async with Client(transport, mode=mode) as client:
            yield client


@pytest.fixture
def harness(monkeypatch):
    app = create_app(
        Settings(
            _env_file=None,
            APP_ENV="test",
            DATABASE_URL="postgresql+psycopg://unused/unused",
            MCP_HTTP_ENABLED=True,
        )
    )
    state = {"entered": 0, "closed": 0, "result": CheckPurchaseResult(DAY, IDENTITY, (offer(),))}

    @contextmanager
    def snapshot(factory, **kwargs):
        assert factory is app.state.session_factory
        assert kwargs["statement_timeout_ms"] == adapter.DB_STATEMENT_TIMEOUT_MS
        assert set(kwargs) <= {"statement_timeout_ms", "cancellation_event"}
        state["entered"] += 1
        try:
            yield "resolver", "repository"
        finally:
            state["closed"] += 1

    def check(*args, **kwargs):
        if "error" in state:
            raise state["error"]
        return state["result"]

    state["check"] = Mock(side_effect=check)
    state["clock"] = Mock(return_value=DAY)
    monkeypatch.setattr(adapter, "purchase_check_snapshot", snapshot)
    monkeypatch.setattr(adapter, "check_purchase", state["check"])
    monkeypatch.setattr(adapter, "uk_evaluation_date", state["clock"])
    return app, state


@pytest.mark.parametrize("mode", ["legacy", "auto", "2026-07-28"])
def test_real_protocol_discovery_dispatch_and_rest_shape(harness, mode):
    app, state = harness

    async def run():
        async with app.router.lifespan_context(app), protocol_client(app, mode) as client:
            tools = await client.list_tools()
            assert len(tools.tools) == 4
            tool = tools.tools[0]
            assert tool.name == "check_purchase"
            assert tool.title == "Check post-purchase benefits"
            assert tool.annotations.read_only_hint and tool.annotations.idempotent_hint
            assert not tool.annotations.destructive_hint and not tool.annotations.open_world_hint
            assert tool.input_schema["additionalProperties"] is False
            assert len(tool.output_schema["oneOf"]) == 2
            result = await client.call_tool("check_purchase", BODY)
            assert not result.is_error
            assert result.structured_content == map_result(state["result"], DAY).model_dump(
                mode="json"
            )
            validate(result.structured_content, tool.output_schema)
            assert result.content[0].text == "resolved; 1 matching variants."
            assert not (await client.list_resources()).resources
            assert not (await client.list_prompts()).prompts

    asyncio.run(run())
    assert state["entered"] == state["closed"] == state["check"].call_count == 1
    state["clock"].assert_called_once()
    args, kwargs = state["check"].call_args
    assert args[0].brand == BODY["brand"]
    assert kwargs == {
        "evaluation_date": DAY,
        "identity_resolver": "resolver",
        "promotion_repository": "repository",
    }


@pytest.mark.parametrize("status", [MatchStatus.NOT_FOUND, MatchStatus.AMBIGUOUS])
def test_unresolved_schema(harness, status):
    app, state = harness
    state["result"] = UnresolvedPurchaseIdentity(
        "model", status, (UUID(int=8), UUID(int=9)) if status == MatchStatus.AMBIGUOUS else ()
    )
    result = app.state.mcp_server.execute(BODY)
    assert not result.is_error
    assert result.structured_content == map_result(state["result"], DAY).model_dump(mode="json")
    validate(result.structured_content, adapter.OUTPUT_SCHEMA)


@pytest.mark.parametrize(
    "changes",
    [
        {"brand": ""},
        {"brand": " "},
        {"brand": 4},
        {"brand": "x" * 256},
        {"brand": "\ufdfa" * 50},
        {"brand": {"url": "http://localhost"}},
        {"purchase_date": "2026-02-30"},
        {"purchase_date": "2026-01-01T00:00:00Z"},
        {"purchase_date": 20260101},
        {"purchase_price": 1},
        {"purchase_price": -1},
        {"purchase_price": "-1"},
        {"purchase_price": "1e2"},
        {"purchase_price": "1.234"},
        {"purchase_price": "£1"},
        {"evaluation_date": "2026-01-01"},
        {"extra": "private"},
    ],
)
def test_strict_invalid_input_never_opens_snapshot(harness, changes):
    app, state = harness
    result = app.state.mcp_server.execute({**BODY, **changes})
    assert result.is_error and result.structured_content is None
    assert json.loads(result.content[0].text)["code"] == "invalid_purchase_request"
    assert state["entered"] == state["check"].call_count == 0


def test_missing_nested_and_oversized(harness):
    app, state = harness
    for value in ({}, {"purchase": BODY}, {**BODY, "extra": "é" * 4096}):
        result = app.state.mcp_server.execute(value)
        assert result.is_error
    assert json.loads(result.content[0].text)["code"] == "request_too_large"
    assert state["entered"] == 0


@pytest.mark.parametrize("price", [None, "0", "0.00", "999999999999.99"])
def test_exact_money(harness, price):
    app, state = harness
    assert not app.state.mcp_server.execute({**BODY, "purchase_price": price}).is_error
    purchase = state["check"].call_args.args[0]
    assert (
        purchase.purchase_price is None if price is None else str(purchase.purchase_price) == price
    )


@pytest.mark.parametrize(
    "error,code",
    [
        (PublishedPromotionDataError(), "published_data_invalid"),
        (IdentityPersistenceError("private"), "eligibility_unavailable"),
        (PromotionPersistenceError("private"), "eligibility_unavailable"),
        (SQLAlchemyError("private"), "eligibility_unavailable"),
        (RuntimeError("private"), "internal_server_error"),
    ],
)
def test_safe_errors_close_snapshot(harness, error, code):
    app, state = harness
    state["error"] = error
    result = app.state.mcp_server.execute(BODY)
    assert result.is_error and result.structured_content is None
    data = json.loads(result.content[0].text)
    assert set(data) == {"code", "message", "request_id"}
    assert data["code"] == code
    UUID(data["request_id"])
    assert "private" not in result.content[0].text
    assert state["closed"] == 1


def test_configuration_default_off_and_production_prohibited():
    settings = Settings(_env_file=None, DATABASE_URL="postgresql+psycopg://unused/unused")
    assert not settings.mcp_http_enabled
    app = create_app(settings)
    assert not hasattr(app.state, "mcp_server")
    assert all(getattr(route, "path", None) != "/" for route in app.routes)
    with pytest.raises(ValidationError, match="prohibited"):
        Settings(
            _env_file=None,
            DATABASE_URL="postgresql+psycopg://unused/unused",
            APP_ENV="production",
            MCP_HTTP_ENABLED=True,
        )


def test_transport_host_origin_and_normal_routes(harness):
    app, _ = harness

    async def run():
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app), base_url="http://localhost:8000"
            ) as http:
                assert (await http.get("/health")).status_code == 200
                assert (await http.get("/openapi.json")).status_code == 200
                assert (
                    await http.post("/mcp", headers={"Host": "attacker.example"}, json={})
                ).status_code == 421
                assert (
                    await http.post("/mcp", headers={"Origin": "http://attacker.example"}, json={})
                ).status_code == 403

    asyncio.run(run())


def test_protocol_safe_execution_errors_and_unknown_tool(harness):
    app, state = harness

    async def run():
        async with app.router.lifespan_context(app), protocol_client(app) as client:
            invalid = await client.call_tool("check_purchase", {**BODY, "purchase_price": 2})
            assert invalid.is_error and invalid.structured_content is None
            assert json.loads(invalid.content[0].text)["code"] == "invalid_purchase_request"
            with pytest.raises(MCPError, match="Unknown tool"):
                await client.call_tool("unknown_tool", BODY)
            assert state["entered"] == 0
            state["error"] = RuntimeError("private raw input and SQL")
            failure = await client.call_tool("check_purchase", BODY)
            assert failure.is_error and failure.structured_content is None
            assert json.loads(failure.content[0].text)["code"] == "internal_server_error"
            assert "private" not in failure.content[0].text

    asyncio.run(run())


def test_serializer_failure_and_sanitized_reporting(harness, monkeypatch):
    app, state = harness
    app.state.settings.sentry_dsn = "https://public@example.ingest.sentry.io/12345"
    capture = Mock()
    scope = Mock()

    @contextmanager
    def new_scope():
        yield scope

    def fail(*args):
        raise RuntimeError("private serializer input")

    monkeypatch.setattr(adapter, "map_result", fail)
    monkeypatch.setattr(adapter.sentry_sdk, "capture_exception", capture)
    monkeypatch.setattr(adapter.sentry_sdk, "new_scope", new_scope)
    result = app.state.mcp_server.execute(BODY)
    assert result.is_error and result.structured_content is None
    assert state["closed"] == 1
    scope.add_event_processor.assert_called_once_with(adapter._safe_exception_event)
    capture.assert_called_once()
    assert "private" not in result.content[0].text


def test_cancellation_waits_for_snapshot_cleanup(harness, monkeypatch):
    import threading

    import anyio

    app, state = harness
    entered, release = threading.Event(), threading.Event()

    def blocked(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=5)
        return state["result"]

    monkeypatch.setattr(adapter, "check_purchase", blocked)

    async def run():
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(app.state.mcp_server.call_tool, "check_purchase", BODY)
            assert await anyio.to_thread.run_sync(entered.wait, 5)
            tasks.cancel_scope.cancel()
            release.set()
        assert state["closed"] == 1

    asyncio.run(run())


@pytest.mark.parametrize("peer", [("127.0.0.1", 12345), ("::1", 12345)])
def test_mounted_loopback_protocol(harness, peer):
    app, state = harness

    async def run():
        async with app.router.lifespan_context(app), protocol_client(app, peer=peer) as client:
            assert [tool.name for tool in (await client.list_tools()).tools] == [
                "check_purchase",
                "get_benefit",
                "get_claim_requirements",
                "get_promotion_source",
            ]
            assert not (await client.call_tool("check_purchase", BODY)).is_error

    asyncio.run(run())
    assert state["entered"] == state["closed"] == 1


@pytest.mark.parametrize(
    "peer",
    [
        None,
        ("192.0.2.1", 80),
        ("localhost", 80),
        ("invalid", 80),
        ("::ffff:192.0.2.1", 80),
        ("127.0.0.1", "80"),
        ("127.0.0.1",),
        ("::1%spoof", 80),
    ],
)
def test_mounted_nonlocal_and_invalid_peers_denied(harness, peer):
    app, state = harness

    async def run():
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app=app, client=peer),
                base_url="http://localhost:8000",
            ) as http:
                response = await http.post(
                    "/mcp",
                    headers={
                        "Host": "localhost:8000",
                        "Origin": "http://localhost:8000",
                        "Forwarded": "for=127.0.0.1",
                        "X-Forwarded-For": "127.0.0.1",
                    },
                    json={
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "tools/call",
                        "params": {"name": "check_purchase", "arguments": BODY},
                    },
                )
                assert response.status_code == 403
                assert (await http.get("/health")).status_code == 200
                assert (await http.get("/openapi.json")).status_code == 200
                assert (await http.get("/docs")).status_code == 200
                assert (await http.post("/api/v1/eligibility/check", json={})).status_code == 422

    asyncio.run(run())
    assert state["entered"] == state["check"].call_count == 0


def test_parent_cancel_signals_worker_before_disconnect_and_waits_for_cleanup(harness, monkeypatch):
    import threading
    from types import SimpleNamespace

    import anyio

    app, state = harness
    entered, exited = threading.Event(), threading.Event()
    events = []
    original_snapshot = adapter.purchase_check_snapshot

    @contextmanager
    def snapshot(*args, **kwargs):
        events.append(kwargs["cancellation_event"])
        with original_snapshot(*args, **kwargs) as pair:
            yield pair

    def blocked(*args, **kwargs):
        entered.set()
        assert events[0].wait(5)
        exited.set()
        return state["result"]

    class ConnectedRequest:
        async def is_disconnected(self):
            return False

    context = SimpleNamespace(request_context=SimpleNamespace(request=ConnectedRequest()))
    monkeypatch.setattr(adapter, "purchase_check_snapshot", snapshot)
    monkeypatch.setattr(adapter, "check_purchase", blocked)
    results = []

    async def run():
        async with anyio.create_task_group() as tasks:

            async def invoke():
                results.append(
                    await app.state.mcp_server.call_tool("check_purchase", BODY, context)
                )

            tasks.start_soon(invoke)
            assert await anyio.to_thread.run_sync(entered.wait, 5)
            tasks.cancel_scope.cancel()
        assert events[0].is_set() and exited.is_set()
        assert state["closed"] == 1
        assert all(result.is_error and result.structured_content is None for result in results)

    asyncio.run(run())


def test_cancel_during_connection_acquisition_closes_session():
    import threading
    from contextlib import contextmanager

    from sqlalchemy.orm import Session

    from app.db.repositories.promotions import PurchaseCheckCancelled, purchase_check_snapshot

    acquiring = threading.Event()
    cancellation = threading.Event()
    cleanup = threading.Event()
    outcome = []

    class AcquiringSession(Session):
        def connection(self, *args, **kwargs):
            acquiring.set()
            assert cancellation.wait(2)
            return None

        def close(self):
            cleanup.set()
            return super().close()

    @contextmanager
    def session_factory():
        with AcquiringSession() as session:
            yield session

    def run_snapshot():
        try:
            with purchase_check_snapshot(
                session_factory,
                statement_timeout_ms=100,
                cancellation_event=cancellation,
            ):
                outcome.append("unexpectedly entered")
        except PurchaseCheckCancelled:
            outcome.append("cancelled")

    worker = threading.Thread(target=run_snapshot)
    worker.start()
    assert acquiring.wait(2)
    cancellation.set()
    worker.join(2)

    assert not worker.is_alive()
    assert outcome == ["cancelled"]
    assert cleanup.is_set()
