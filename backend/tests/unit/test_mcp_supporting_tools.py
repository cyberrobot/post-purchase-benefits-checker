import asyncio
import json
from contextlib import contextmanager
from dataclasses import replace
from decimal import Decimal
from threading import Event
from unittest.mock import Mock
from uuid import UUID

import pytest
from jsonschema import validate
from sqlalchemy.exc import SQLAlchemyError

from app.application.promotion_details import LookupNotFound, get_published_details
from app.application.purchase_check_details import PublishedBenefit, PublishedPromotionDataError
from app.domain.benefits import Benefit
from app.domain.promotion_lifecycle import PromotionStatus
from app.domain.rewards import PercentageReward, ProductRewardValue, ProductSpecificReward
from app.mcp import server as adapter
from app.mcp.schemas import LOOKUP_SCHEMAS, Reward
from tests.unit.test_mcp_check_purchase import harness as harness
from tests.unit.test_mcp_check_purchase import protocol_client
from tests.unit.test_purchase_check import DETAIL, PRODUCT, VARIANT

BENEFIT = DETAIL.benefits[0].benefit_id
SOURCE = DETAIL.sources[0].source_id
ARGUMENTS = {
    "get_benefit": {"promotion_variant_id": str(VARIANT), "benefit_id": str(BENEFIT)},
    "get_claim_requirements": {"promotion_variant_id": str(VARIANT)},
    "get_promotion_source": {"promotion_variant_id": str(VARIANT), "source_id": str(SOURCE)},
}


@pytest.fixture
def lookup_harness(harness, monkeypatch):
    app, state = harness
    state["detail"] = DETAIL

    def load(variant_id):
        if "error" in state:
            raise state["error"]
        return state["detail"] if variant_id == VARIANT else None

    repository = Mock(load_published_variant=Mock(side_effect=load))
    state["repository"] = repository

    @contextmanager
    def snapshot(factory, **options):
        assert options["statement_timeout_ms"] == 5000
        state["entered"] += 1
        try:
            yield None, repository
        finally:
            state["closed"] += 1

    monkeypatch.setattr(adapter, "purchase_check_snapshot", snapshot)
    return app, state


DEFAULT_ARGUMENTS = object()


def execute(harness, name, arguments=DEFAULT_ARGUMENTS):
    return harness[0].state.mcp_server.execute_lookup(
        (name, ARGUMENTS[name] if arguments is DEFAULT_ARGUMENTS else arguments)
    )


def code(result):
    assert result.is_error and result.structured_content is None
    error = json.loads(result.content[0].text)
    assert set(error) == {"code", "message", "request_id"}
    UUID(error["request_id"])
    assert "private" not in result.content[0].text
    return error["code"]


def test_discovery_and_success_over_real_protocol(lookup_harness):
    app, state = lookup_harness

    async def run():
        async with app.router.lifespan_context(app), protocol_client(app) as client:
            tools = (await client.list_tools()).tools
            assert [t.name for t in tools] == ["check_purchase", *LOOKUP_SCHEMAS]
            for tool in tools[1:]:
                assert tool.title and tool.description
                assert tool.input_schema["additionalProperties"] is False
                assert tool.output_schema["additionalProperties"] is False
                assert tool.annotations.read_only_hint and tool.annotations.idempotent_hint
                assert (
                    not tool.annotations.destructive_hint and not tool.annotations.open_world_hint
                )
                for _ in range(2):
                    result = await client.call_tool(tool.name, ARGUMENTS[tool.name])
                    assert not result.is_error
                    validate(result.structured_content, tool.output_schema)
                    assert result.content[0].text
            assert not (await client.list_resources()).resources
            assert not (await client.list_prompts()).prompts

    asyncio.run(run())
    assert state["entered"] == state["closed"] == 6
    state["check"].assert_not_called()
    state["clock"].assert_not_called()


@pytest.mark.parametrize("name", ARGUMENTS)
@pytest.mark.parametrize(
    "invalid",
    [
        None,
        [],
        42,
        {},
        {"promotion_variant_id": 4},
        {"promotion_variant_id": "bad"},
        {"promotion_variant_id": {}},
        {"promotion_variant_id": str(VARIANT), "extra": 1},
        {"promotion_variant_id": str(VARIANT).replace("-", "")},
    ],
)
def test_invalid_never_opens_snapshot(lookup_harness, name, invalid):
    assert code(execute(lookup_harness, name, invalid)) == "invalid_lookup_request"
    assert lookup_harness[1]["entered"] == 0


def test_size_ceiling_and_uuid_case(lookup_harness):
    args = {**ARGUMENTS["get_claim_requirements"], "extra": ""}
    base = len(json.dumps(args).encode())
    args["extra"] = "x" * (8192 - base)
    assert code(execute(lookup_harness, "get_claim_requirements", args)) == "invalid_lookup_request"
    args["extra"] += "x"
    assert code(execute(lookup_harness, "get_claim_requirements", args)) == "request_too_large"
    assert lookup_harness[1]["entered"] == 0
    args = {"promotion_variant_id": str(VARIANT).upper()}
    assert not execute(lookup_harness, "get_claim_requirements", args).is_error


@pytest.mark.parametrize("status", list(PromotionStatus))
def test_application_publication_gate(lookup_harness, status):
    app, state = lookup_harness
    state["detail"] = replace(DETAIL, promotion_status=status)
    if status in {PromotionStatus.ACTIVE, PromotionStatus.EXPIRED}:
        assert (
            get_published_details(state["repository"], VARIANT).details.promotion_status == status
        )
    else:
        with pytest.raises(LookupNotFound):
            get_published_details(state["repository"], VARIANT)
        assert code(execute(lookup_harness, "get_claim_requirements")) == "not_found"


@pytest.mark.parametrize(
    "name,field",
    [
        ("get_benefit", "benefit_id"),
        ("get_promotion_source", "source_id"),
        ("get_claim_requirements", "promotion_variant_id"),
    ],
)
def test_wrong_association(lookup_harness, name, field):
    assert (
        code(execute(lookup_harness, name, {**ARGUMENTS[name], field: str(UUID(int=999))}))
        == "not_found"
    )


@pytest.mark.parametrize(
    "reward,expected",
    [
        (None, None),
        (PercentageReward(Decimal("12.3456")), "12.3456"),
        (DETAIL.benefits[0].reward, "100"),
    ],
)
def test_static_rewards(lookup_harness, reward, expected):
    state = lookup_harness[1]
    state["detail"] = replace(DETAIL, benefits=(replace(DETAIL.benefits[0], reward=reward),))
    data = execute(lookup_harness, "get_benefit").structured_content
    if reward is None:
        assert data["reward"] is None
    else:
        value = data["reward"]
        assert (value["percentage"] or value["fixed_amount_gbp"]) == expected
        assert value["product_lookup_status"] == "not_applicable"
    assert (
        code(
            execute(
                lookup_harness,
                "get_benefit",
                {**ARGUMENTS["get_benefit"], "product_id": str(PRODUCT)},
            )
        )
        == "invalid_lookup_request"
    )


def test_single_product_and_missing_configured_amount(lookup_harness):
    state = lookup_harness[1]
    reward = ProductSpecificReward((ProductRewardValue(PRODUCT, Decimal("123.45")),))
    state["detail"] = replace(DETAIL, benefits=(replace(DETAIL.benefits[0], reward=reward),))
    result = execute(lookup_harness, "get_benefit").structured_content["reward"]
    assert result["product_lookup_status"] == "product_id_required"
    result = execute(
        lookup_harness, "get_benefit", {**ARGUMENTS["get_benefit"], "product_id": str(PRODUCT)}
    ).structured_content["reward"]
    assert result["product_amount_gbp"] == "123.45"
    assert result["product_lookup_status"] == "configured"
    assert "values" not in result
    assert (
        code(
            execute(
                lookup_harness,
                "get_benefit",
                {**ARGUMENTS["get_benefit"], "product_id": str(UUID(int=99))},
            )
        )
        == "not_found"
    )
    state["detail"] = replace(state["detail"], product_ids=frozenset({PRODUCT, UUID(int=99)}))
    assert code(execute(lookup_harness, "get_benefit")) == "published_data_invalid"


def test_requirements_sort_empty_and_non_cashback(lookup_harness):
    state = lookup_harness[1]
    data = execute(lookup_harness, "get_claim_requirements").structured_content
    assert [r["requirement_id"] for r in data["requirements"]] == sorted(
        str(r.requirement_id) for r in DETAIL.requirements
    )
    assert data["claim_url"] == "https://example.com/claim"
    state["detail"] = replace(
        DETAIL,
        requirements=(),
        benefits=(PublishedBenefit(BENEFIT, Benefit("extended_warranty", "Warranty")),),
    )
    data = execute(lookup_harness, "get_claim_requirements").structured_content
    assert data["requirements"] == [] and data["requirements_recorded"] is False
    assert execute(lookup_harness, "get_benefit").structured_content["reward"] is None


@pytest.mark.parametrize("role", ["primary", "claim", "supporting", "terms"])
def test_source_role_and_independent_verification(lookup_harness, role):
    state = lookup_harness[1]
    supporting = replace(DETAIL.sources[0], role=role, verified_at=None)
    if role in {"primary", "claim"}:
        selected = next(s for s in DETAIL.sources if s.role == role)
    else:
        selected = supporting
        state["detail"] = replace(
            DETAIL, sources=tuple(s for s in DETAIL.sources if s.role != "supporting") + (selected,)
        )
    data = execute(
        lookup_harness,
        "get_promotion_source",
        {"promotion_variant_id": str(VARIANT), "source_id": str(selected.source_id)},
    ).structured_content
    assert data["is_official_primary_source"] == (role == "primary")
    assert (data["verified_at"] is None) == (role in {"supporting", "terms"})
    assert data["last_verified_at"] is not None


@pytest.mark.parametrize(
    "error,expected",
    [
        (PublishedPromotionDataError(), "published_data_invalid"),
        (SQLAlchemyError("private"), "lookup_unavailable"),
        (RuntimeError("private"), "internal_server_error"),
        (adapter.PurchaseCheckCancelled(), "lookup_unavailable"),
    ],
)
def test_errors_cleanup(lookup_harness, error, expected):
    lookup_harness[1]["error"] = error
    assert code(execute(lookup_harness, "get_claim_requirements")) == expected
    assert lookup_harness[1]["closed"] == 1


def test_broken_provenance_and_response_bound(lookup_harness):
    state = lookup_harness[1]
    state["detail"] = replace(DETAIL, sources=())
    assert code(execute(lookup_harness, "get_claim_requirements")) == "published_data_invalid"
    state["detail"] = replace(
        DETAIL, benefits=(replace(DETAIL.benefits[0], benefit=Benefit("cashback", "x" * 65536)),)
    )
    assert code(execute(lookup_harness, "get_benefit")) == "published_data_invalid"
    assert state["closed"] == 2


def test_non_cashback_benefit_cannot_have_reward(lookup_harness):
    state = lookup_harness[1]
    state["detail"] = replace(
        DETAIL,
        benefits=(
            replace(
                DETAIL.benefits[0],
                benefit=Benefit("extended_warranty", "Warranty"),
            ),
        ),
    )
    assert code(execute(lookup_harness, "get_benefit")) == "published_data_invalid"


def test_cancelled_before_query(lookup_harness):
    event = Event()
    event.set()
    result = lookup_harness[0].state.mcp_server.execute_lookup(
        ("get_claim_requirements", ARGUMENTS["get_claim_requirements"]), event
    )
    assert code(result) == "lookup_unavailable"
    lookup_harness[1]["repository"].load_published_variant.assert_not_called()


def test_reward_shape_rejected():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Reward(
            reward_type="fixed_amount",
            fixed_amount_gbp=None,
            percentage="4",
            product_id=None,
            product_amount_gbp=None,
            product_lookup_status="not_applicable",
        )


def test_every_requirement_kind_null_description(lookup_harness):
    from app.application.purchase_check_details import PublishedRequirement
    from app.domain.requirements import Requirement, RequirementType

    lookup_harness[1]["detail"] = replace(
        DETAIL,
        requirements=tuple(
            PublishedRequirement(UUID(int=100 + i), Requirement(kind))
            for i, kind in enumerate(RequirementType)
        ),
    )
    data = execute(lookup_harness, "get_claim_requirements").structured_content
    assert {r["requirement_type"] for r in data["requirements"]} == set(RequirementType)
    assert all(r["description"] is None for r in data["requirements"])


def test_serialization_failure_and_safe_reporting(lookup_harness, monkeypatch):
    from app.mcp.schemas import RequirementsOutput

    app, state = lookup_harness
    app.state.settings.sentry_dsn = "https://public@example.ingest.sentry.io/12345"
    capture, scope = Mock(), Mock()

    @contextmanager
    def new_scope():
        yield scope

    def fail(*args, **kwargs):
        raise RuntimeError("private serializer data")

    monkeypatch.setattr(RequirementsOutput, "model_dump", fail)
    monkeypatch.setattr(adapter.sentry_sdk, "new_scope", new_scope)
    monkeypatch.setattr(adapter.sentry_sdk, "capture_exception", capture)
    assert code(execute(lookup_harness, "get_claim_requirements")) == "internal_server_error"
    assert state["closed"] == 1
    scope.add_event_processor.assert_called_once_with(adapter._safe_exception_event)
    capture.assert_called_once()


def test_parent_cancellation_waits_for_lookup_cleanup(lookup_harness, monkeypatch):
    import threading

    import anyio

    app, state = lookup_harness
    entered = threading.Event()
    cancellation = []
    original_snapshot = adapter.purchase_check_snapshot

    @contextmanager
    def tracked(*args, **kwargs):
        cancellation.append(kwargs["cancellation_event"])
        with original_snapshot(*args, **kwargs) as pair:
            yield pair

    def blocked(*args):
        entered.set()
        assert cancellation[0].wait(5)
        return DETAIL

    monkeypatch.setattr(adapter, "purchase_check_snapshot", tracked)
    state["repository"].load_published_variant.side_effect = blocked

    async def run():
        async with anyio.create_task_group() as tasks:
            tasks.start_soon(
                app.state.mcp_server.call_tool,
                "get_claim_requirements",
                ARGUMENTS["get_claim_requirements"],
            )
            assert await anyio.to_thread.run_sync(entered.wait, 5)
            tasks.cancel_scope.cancel()
        assert state["closed"] == 1

    asyncio.run(run())
